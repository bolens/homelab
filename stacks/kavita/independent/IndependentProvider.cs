// Modified 2026-10-22 for independent provider support. GPL-3.0.
using System;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Kavita.Common;

public static class IndependentProvider
{
    public static bool Enabled => !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("KAVITA_PROVIDER_URL"));
    public static string Url
    {
        get
        {
            var raw = Environment.GetEnvironmentVariable("KAVITA_PROVIDER_URL") ?? "";
            if (!Uri.TryCreate(raw, UriKind.Absolute, out var uri) ||
                (uri.Scheme != "http" && uri.Scheme != "https") ||
                !string.IsNullOrEmpty(uri.UserInfo) || uri.AbsolutePath != "/" ||
                !string.IsNullOrEmpty(uri.Query) || !string.IsNullOrEmpty(uri.Fragment) ||
                uri.Host.Equals("plus.kavitareader.com", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Invalid independent provider origin");
            return raw.TrimEnd('/');
        }
    }
    public static string Key => File.ReadAllText(Environment.GetEnvironmentVariable("KAVITA_PROVIDER_KEY_FILE")
        ?? throw new InvalidOperationException("Independent provider key file is required")).Trim();
    private static readonly HttpClient Client = new(new HttpClientHandler { AllowAutoRedirect = false })
        { Timeout = TimeSpan.FromSeconds(10), MaxResponseContentBufferSize = 262144 };
    private static readonly SemaphoreSlim Lock = new(1, 1);
    private static DateTime Expires;
    private static JsonElement Cached;
    private sealed record ActionSnapshot(JsonElement Manifest, string Origin, string KeyHash);
    private static ActionSnapshot? Actions;
    private static string ActionFile => Environment.GetEnvironmentVariable("KAVITA_PROVIDER_ACTIONS_FILE")
        ?? Path.Combine(AppContext.BaseDirectory, "config", "independent-actions.json");
    private static string KeyHash => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(Key)));
    private static ActionSnapshot? CreationSnapshot()
    {
        if (!Enabled) return null;
        try
        {
            var snapshot = System.Threading.Volatile.Read(ref Actions);
            if (snapshot != null && snapshot.Origin == Url && snapshot.KeyHash == KeyHash) return snapshot;
            // Persisted capabilities authorize local retention only. They never
            // replace the current manifest required before an external write.
            var info = new FileInfo(ActionFile);
            if (!info.Exists || info.Length > 524288) return null;
            using var envelope = JsonDocument.Parse(File.ReadAllText(ActionFile));
            var payload = envelope.RootElement.GetProperty("payload").GetString()!;
            var signature = Convert.FromHexString(envelope.RootElement.GetProperty("signature").GetString()!);
            var expected = HMACSHA256.HashData(Encoding.UTF8.GetBytes(Key), Encoding.UTF8.GetBytes(payload));
            if (!CryptographicOperations.FixedTimeEquals(signature, expected)) return null;
            using var doc = JsonDocument.Parse(payload);
            if (doc.RootElement.GetProperty("origin").GetString() != Url) return null;
            var manifest = doc.RootElement.GetProperty("manifest");
            ValidateManifest(manifest);
            var restored = new ActionSnapshot(manifest.Clone(), Url, KeyHash);
            // A concurrent valid manifest may have revoked an action while the
            // file was being read. Never replace that newer in-memory decision.
            var concurrent = Interlocked.CompareExchange(ref Actions, restored, snapshot);
            return ReferenceEquals(concurrent, snapshot) ? restored :
                concurrent != null && concurrent.Origin == Url && concurrent.KeyHash == KeyHash ? concurrent : null;
        }
        catch (Exception) { return null; }
    }
    private static bool SaveActions(JsonElement manifest)
    {
        var temporary = ActionFile + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            var payload = JsonSerializer.Serialize(new { origin = Url, manifest });
            var signature = Convert.ToHexString(HMACSHA256.HashData(Encoding.UTF8.GetBytes(Key), Encoding.UTF8.GetBytes(payload)));
            var data = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(new { payload, signature }));
            if (data.Length > 524288) return false;
            using (var file = new FileStream(temporary, new FileStreamOptions {
                Mode = FileMode.CreateNew, Access = FileAccess.Write, Share = FileShare.None,
                UnixCreateMode = UnixFileMode.UserRead | UnixFileMode.UserWrite }))
            { file.Write(data); file.Flush(true); }
            File.Move(temporary, ActionFile, true);
            return true;
        }
        catch (Exception) { return false; }
        finally { try { File.Delete(temporary); } catch (Exception) { } }
    }
    private static void ValidateManifest(JsonElement root)
    {
        if (root.GetProperty("protocolVersion").GetInt32() != 1 || root.GetProperty("mode").GetString() != "independent" ||
            root.GetProperty("providers").ValueKind != JsonValueKind.Array || root.GetProperty("limitations").ValueKind != JsonValueKind.Array)
            throw new InvalidOperationException();
        foreach (var provider in root.GetProperty("providers").EnumerateArray())
        {
            _ = provider.GetProperty("name").GetString();
            _ = provider.GetProperty("available").GetBoolean();
            foreach (var capability in provider.GetProperty("capabilities").EnumerateArray()) _ = capability.GetString();
        }
    }
    public static bool KnownScrobbleAction(int provider, int evt) =>
        CreationSnapshot() is { } snapshot && IndependentScrobblePolicy.Allows(snapshot.Manifest, provider, evt);
    public static async Task<bool> CanQueueScrobbleEvents(CancellationToken ct = default)
    {
        _ = await Manifest(ct);
        var snapshot = CreationSnapshot();
        return snapshot != null && new[] {1, 2, 5, 6}.Any(provider =>
            Enumerable.Range(0, 6).Any(evt => IndependentScrobblePolicy.Allows(snapshot.Manifest, provider, evt)));
    }
    public static async Task<bool> ScrobbleAction(int provider, int evt, CancellationToken ct = default) =>
        IndependentScrobblePolicy.Allows(await Manifest(ct), provider, evt);

    private static JsonElement Unavailable => JsonSerializer.SerializeToElement(new {
        protocolVersion = 1, mode = "independent", providers = Array.Empty<object>(),
        limitations = new[] { "Independent provider is unavailable or returned an incompatible manifest." }
    });
    public static async Task<JsonElement> Manifest(CancellationToken ct = default)
    {
        if (!Enabled) return JsonSerializer.SerializeToElement(new {
            protocolVersion = 1, mode = "official", providers = Array.Empty<object>(), limitations = Array.Empty<string>() });
        await Lock.WaitAsync(ct);
        try
        {
            if (DateTime.UtcNow < Expires) return Cached;
            var valid = true;
            try
            {
                using var request = new HttpRequestMessage(HttpMethod.Get, Url + "/capabilities");
                var key = Key;
                if (key.Length < 32 || key.Contains('\r') || key.Contains('\n')) throw new InvalidOperationException();
                request.Headers.Add("X-Provider-Key", key);
                using var response = await Client.SendAsync(request, HttpCompletionOption.ResponseContentRead, ct);
                response.EnsureSuccessStatusCode();
                using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync(ct));
                var root = document.RootElement;
                ValidateManifest(root);
                Cached = root.Clone();
            }
            catch (Exception) { Cached = Unavailable; valid = false; }
            Expires = DateTime.UtcNow.AddSeconds(30);
            if (valid)
            {
                System.Threading.Volatile.Write(ref Actions, new ActionSnapshot(Cached, Url, KeyHash));
                if (!SaveActions(Cached))
                {
                    Cached = JsonSerializer.SerializeToElement(new {
                        protocolVersion = 1, mode = "independent", providers = Cached.GetProperty("providers"),
                        limitations = Cached.GetProperty("limitations").EnumerateArray().Select(x => x.GetString())
                            .Append("Creation snapshot could not be saved; restart retention is unavailable.").ToArray()
                    });
                }
            }
            return Cached;
        }
        finally { Lock.Release(); }
    }
    public static async Task<JsonElement> PostOAuth(string path, object payload, CancellationToken ct = default)
    {
        if (!Enabled || (path != "/oauth/start" && path != "/oauth/complete"))
            throw new InvalidOperationException("Independent OAuth route unavailable");
        return await PostPrivate(path, payload, ct);
    }
    private static async Task<JsonElement> PostPrivate(string path, object payload, CancellationToken ct)
    {
        var key = Key;
        if (key.Length < 32 || key.Contains('\r') || key.Contains('\n'))
            throw new InvalidOperationException("Independent provider key invalid");
        using var request = new HttpRequestMessage(HttpMethod.Post, Url + path);
        request.Headers.Add("X-Provider-Key", key);
        request.Content = new StringContent(JsonSerializer.Serialize(payload), System.Text.Encoding.UTF8, "application/json");
        using var response = await Client.SendAsync(request, HttpCompletionOption.ResponseContentRead, ct);
        response.EnsureSuccessStatusCode();
        using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync(ct));
        return document.RootElement.Clone();
    }
    public static int? OAuthUpstreamFor(int provider) => provider switch { 1 => 2, 2 => 3, 5 => 4, 6 => 1, _ => null };
    public static async Task<DateTime?> KnownTokenExpiry(int upstream, string token, CancellationToken ct = default)
    {
        if (!Enabled || upstream < 1 || upstream > 4 || string.IsNullOrWhiteSpace(token)) return null;
        try
        {
            var result = await PostPrivate("/api/v3/oauth/token-expiration", new { upstream, accessToken = token }, ct);
            if (!result.GetProperty("isSuccess").GetBoolean()) return null;
            var data = result.GetProperty("data");
            if (data.ValueKind != JsonValueKind.String || !data.TryGetDateTime(out var expiry) ||
                expiry == DateTime.MinValue || expiry == DateTime.MaxValue) return null;
            return expiry.ToUniversalTime();
        }
        catch (Exception) { return null; }
    }
    public static async Task<bool> Has(string capability, CancellationToken ct = default)
    {
        var manifest = await Manifest(ct);
        return Enabled && manifest.GetProperty("providers").EnumerateArray().Any(provider =>
            provider.GetProperty("available").GetBoolean() && provider.GetProperty("capabilities")
                .EnumerateArray().Any(value => value.GetString() == capability));
    }
    public static async Task<bool> Any(CancellationToken ct = default)
    {
        var manifest = await Manifest(ct);
        return Enabled && manifest.GetProperty("providers").EnumerateArray().Any(provider =>
            provider.GetProperty("available").GetBoolean() && provider.GetProperty("capabilities").GetArrayLength() > 0);
    }
}
