// Modified 2026-10-22. GPL-3.0. Shared admission for personal sync only.
using System;
using System.Linq;
using System.Text.Json;
namespace Kavita.Common;

public static class IndependentScrobblePolicy
{
    public static string? ProviderName(int provider) => provider switch {
        1 => "AniList", 2 => "MyAnimeList", 5 => "Hardcover", 6 => "MangaBaka", _ => null };
    public static string? Action(int evt) => evt switch {
        0 => "progress", 1 => "wantToRead", 2 => "safeWantToReadRemoval",
        3 => "ratings", 4 => "reviews", 5 => "readingStatus", _ => null };
    public static bool Has(JsonElement manifest, int provider, string action)
    {
        try
        {
            var name = ProviderName(provider);
            if (name == null || manifest.GetProperty("mode").GetString() != "independent") return false;
            var entries = manifest.GetProperty("providers").EnumerateArray()
                .Where(p => p.GetProperty("name").GetString() == name).ToArray();
            if (entries.Length != 1 || !entries[0].GetProperty("available").GetBoolean()) return false;
            // Public metadata reviews must never enable personal review writes.
            var sync = entries[0].GetProperty("adapters").GetProperty("sync");
            var capabilities = sync.GetProperty("capabilities").EnumerateArray().ToArray();
            if (capabilities.Any(c => c.ValueKind != JsonValueKind.String)) return false;
            return sync.GetProperty("available").GetBoolean() && capabilities.Any(c => c.GetString() == action ||
                    action == "progress" && c.GetString() == "progressWithExistingEdition");
        }
        catch (Exception) { return false; }
    }
    public static bool Allows(JsonElement manifest, int provider, int evt) =>
        Action(evt) is string action && Has(manifest, provider, action);
    public static bool AllowsPayload(JsonElement manifest, int provider, int evt, int reads,
        int? status, int? visibility)
    {
        if (!Allows(manifest, provider, evt)) return false;
        if (evt == 0 && (reads < 0 || reads > 1)) return false;
        if (evt == 5 && status is not (1 or 2 or 4 or 5)) return false;
        if (evt == 4 && (visibility is not (0 or 1 or 2) ||
            visibility == 1 && !Has(manifest, provider, "friendsOnlyReviews"))) return false;
        return true;
    }
}
