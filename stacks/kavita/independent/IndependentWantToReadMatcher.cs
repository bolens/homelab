// Modified 2026-10-22. Exact identity matching only. GPL-3.0.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text.RegularExpressions;
using Kavita.Models.DTOs.KavitaPlus.Metadata;
using Kavita.Models.Entities;
using Kavita.Models.Entities.Enums;

namespace Kavita.Services.Plus;

public static class IndependentWantToReadMatcher
{
    public static long? Identity(ExternalSeriesDetailDto external) => external.Provider switch
    {
        ScrobbleProvider.AniList when external.AniListId is > 0 => external.AniListId,
        ScrobbleProvider.Mal when external.MALId is > 0 => external.MALId,
        ScrobbleProvider.Hardcover when external.HardcoverId is > 0 => external.HardcoverId,
        ScrobbleProvider.MangaBaka when external.MangabakaId is > 0 => external.MangabakaId,
        _ => null
    };

    private static HashSet<long> LinkIdentities(string? links, ScrobbleProvider provider)
    {
        var identities = new HashSet<long>();
        foreach (var text in Regex.Split(links ?? "", @"[\s,;]+", RegexOptions.None, TimeSpan.FromSeconds(1)))
        {
            if (!Uri.TryCreate(text, UriKind.Absolute, out var uri) ||
                (uri.Scheme != "https" && uri.Scheme != "http") || !uri.IsDefaultPort ||
                !string.IsNullOrEmpty(uri.UserInfo) || !string.IsNullOrEmpty(uri.Query) || !string.IsNullOrEmpty(uri.Fragment)) continue;
            var expected = provider == ScrobbleProvider.AniList ? "anilist.co" : "myanimelist.net";
            if (uri.Host != expected && uri.Host != "www." + expected) continue;
            var segments = uri.AbsolutePath.Trim('/').Split('/');
            if (segments.Length < 2 || segments[0] != "manga" ||
                segments.Length > (provider == ScrobbleProvider.Mal ? 3 : 2)) continue;
            if (long.TryParse(segments[1], NumberStyles.None, CultureInfo.InvariantCulture, out var id) && id > 0)
                identities.Add(id);
        }
        return identities;
    }

    public static bool Matches(ExternalSeriesDetailDto external, Series local)
    {
        var identity = Identity(external);
        if (!identity.HasValue || local.Id <= 0) return false;
        if (external.Provider == ScrobbleProvider.Hardcover)
            return local.HardcoverId == identity.Value && local.IsStandAlone == external.IsStandAlone;
        if (external.Provider == ScrobbleProvider.MangaBaka)
            return local.MangaBakaId == identity.Value;
        var stored = external.Provider == ScrobbleProvider.AniList ? local.AniListId : local.MalId;
        var links = LinkIdentities(local.Metadata?.WebLinks, external.Provider);
        if (links.Count > 1 || (stored > 0 && links.Any(id => id != stored))) return false;
        return stored > 0 ? stored == identity.Value : links.Count == 1 && links.Contains(identity.Value);
    }

    public static int? Resolve(ExternalSeriesDetailDto external, IEnumerable<Series> visibleCandidates,
        IEnumerable<int>? visibleChapterSeriesIds = null)
    {
        if (!Identity(external).HasValue) return null;
        var matched = visibleCandidates.Where(local => Matches(external, local)).Select(local => local.Id).ToHashSet();
        if (external.Provider == ScrobbleProvider.Hardcover && external.IsStandAlone && visibleChapterSeriesIds != null)
            matched.UnionWith(visibleChapterSeriesIds.Where(id => id > 0));
        return matched.Count == 1 ? matched.Single() : null;
    }
}
