// Modified 2026-10-22. Independent OAuth boundary checks. GPL-3.0.
using System;
using System.Linq;

namespace Kavita.Common;

public static class IndependentOAuth
{
    public const string CookieName = "kavita-independent-oauth";
    public static Uri PublicUrl
    {
        get
        {
            var raw = Environment.GetEnvironmentVariable("KAVITA_PUBLIC_URL") ?? "";
            if (!Uri.TryCreate(raw, UriKind.Absolute, out var uri) ||
                (uri.Scheme != "https" && !(uri.Scheme == "http" && uri.IsLoopback)) ||
                !string.IsNullOrEmpty(uri.UserInfo) || !string.IsNullOrEmpty(uri.Query) ||
                !string.IsNullOrEmpty(uri.Fragment) || uri.AbsolutePath.Contains("//"))
                throw new InvalidOperationException("Set KAVITA_PUBLIC_URL to the fixed public HTTPS Kavita URL");
            return uri;
        }
    }
    public static string CallbackUrl => PublicUrl.AbsoluteUri.TrimEnd('/') + "/api/oauth/independent-callback";
    public static string CookiePath => new Uri(CallbackUrl).AbsolutePath;
    public static string SettingsUrl => PublicUrl.AbsolutePath.TrimEnd('/') + "/settings?loading=true#scrobble-settings";
    public static bool ValidAuthorizationUrl(int upstream, string authorizationUrl, string state)
    {
        var expected = upstream switch
        {
            1 => "https://mangabaka.org/auth/oauth2/authorize",
            2 => "https://anilist.co/api/v2/oauth/authorize",
            3 => "https://myanimelist.net/v1/oauth2/authorize",
            4 => "https://hardcover.app/oauth2/authorize",
            _ => ""
        };
        if (state.Length < 32 || state.Length > 256 ||
            !Uri.TryCreate(authorizationUrl, UriKind.Absolute, out var uri) ||
            uri.GetLeftPart(UriPartial.Path) != expected || !string.IsNullOrEmpty(uri.UserInfo) ||
            !string.IsNullOrEmpty(uri.Fragment)) return false;
        try
        {
            var states = uri.Query.TrimStart('?').Split('&').Select(item => item.Split('=', 2))
                .Where(item => Uri.UnescapeDataString(item[0]) == "state").ToArray();
            return states.Length == 1 && states[0].Length == 2 && Uri.UnescapeDataString(states[0][1]) == state;
        }
        catch (Exception) { return false; }
    }
}

public sealed record IndependentOAuthBinding
{
    public string ApiKey { get; init; } = "";
    public int Upstream { get; init; }
    public string BrowserHash { get; init; } = "";
    public long ExpiresUnix { get; init; }
}
