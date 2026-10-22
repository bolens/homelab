#!/usr/bin/env python3
"""Apply a fail-closed, reviewable patch to an isolated pinned source export."""
import argparse
import hashlib
from pathlib import Path
import re
import shutil

SOURCE_SHA = "879b8b73eb41d66f88dde8eb874cc99a3397eb11"
HERE = Path(__file__).resolve().parent


def replace(root, path, old, new, count=1):
    target = root / path
    source = target.read_text(encoding="utf-8-sig")
    if source.count(old) != count:
        raise ValueError(f"Unexpected pinned source anchor: {path}")
    target.write_text(source.replace(old, new), encoding="utf-8")


def patch(root):
    # Hash inventory prevents silently applying to another release, including partly patched trees.
    for line in (HERE / "source.sha256").read_text().splitlines():
        digest, path = line.split("  ", 1)
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Pinned source mismatch: {path}")
    shutil.copyfile(HERE / "IndependentProvider.cs", root / "Kavita.Common/IndependentProvider.cs")
    shutil.copyfile(HERE / "independent-actions.ts", root / "UI/Web/src/app/_services/independent-actions.ts")
    shutil.copyfile(HERE / "IndependentScrobblePolicy.cs", root / "Kavita.Common/IndependentScrobblePolicy.cs")
    shutil.copyfile(HERE / "IndependentOAuth.cs", root / "Kavita.Common/IndependentOAuth.cs")
    shutil.copyfile(HERE / "IndependentWantToReadMatcher.cs", root / "Kavita.Services/Plus/IndependentWantToReadMatcher.cs")
    replace(root, "Kavita.Common/Configuration.cs", "    private static string GetKavitaPlusApiUrl()\n    {",
            "    private static string GetKavitaPlusApiUrl()\n    {\n        if (IndependentProvider.Enabled) return IndependentProvider.Url;")
    replace(root, "Kavita.Common/Extensions/FlurlExtensions.cs", "        return request\n            .WithHeader(HeaderNames.Accept, \"application/json\")", '''        if (IndependentProvider.Enabled)
        {
            var uri = new Uri(request);
            if (uri.GetLeftPart(UriPartial.Authority) != IndependentProvider.Url ||
                uri.AbsolutePath.StartsWith("/api/license", StringComparison.OrdinalIgnoreCase) ||
                uri.AbsolutePath.StartsWith("/api/stats", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Hosted subscription operations are unavailable in independent mode");
            return request.WithHeader("X-Provider-Key", IndependentProvider.Key)
                .WithHeader(HeaderNames.Accept, "application/json")
                .WithHeader(HeaderNames.ContentType, "application/json")
                .WithTimeout(TimeSpan.FromSeconds(30)).WithSettings(s => {
                    s.Redirects.Enabled = false;
                    s.JsonSerializer = new Flurl.Http.Configuration.DefaultJsonSerializer(
                        new System.Text.Json.JsonSerializerOptions(System.Text.Json.JsonSerializerDefaults.Web));
                });
        }
        return request
            .WithHeader(HeaderNames.Accept, "application/json")''', count=2)
    # WithBasicHeaders is unrelated to the independent backend and remains stock.
    # Undo the independent insertion in WithBasicHeaders introduced by the shared anchor.
    path = root / "Kavita.Common/Extensions/FlurlExtensions.cs"
    text = path.read_text()
    start = text.index("    public static IFlurlRequest WithBasicHeaders")
    tail = text[start:]
    begin, end = tail.index("        if (IndependentProvider.Enabled)"), tail.index("        return request\n")
    path.write_text(text[:start] + tail[:begin] + tail[end:])
    for signature, result in [
        ("public async Task<bool> HasActiveLicense(bool forceCheck = false, CancellationToken ct = default)", "false"),
        ("public async Task<bool> HasActiveSubscription(string? license, CancellationToken ct = default)", "false"),
        ("public async Task<LicenseInfoDto?> GetLicenseInfo(bool forceCheck = false, CancellationToken ct = default)", "null"),
    ]:
        replace(root, "Kavita.Services/Plus/LicenseService.cs", signature + "\n    {",
                signature + "\n    {\n        if (IndependentProvider.Enabled) return " + result + ";")
    # Functional checks are distinct from paid subscription checks, with the original path retained verbatim.
    groups = {
        "Kavita.Services/Plus/ExternalMetadataService.cs": "metadata",
        "Kavita.Services/Plus/ScrobblingService.cs": "scrobbling",
        "Kavita.Services/Plus/SmartCollectionSyncService.cs": "stacks",
        "Kavita.Services/Plus/WantToReadSyncService.cs": "wantToRead",
        "Kavita.Services/TaskScheduler.cs": "*",
        "Kavita.Server/Attributes/KPlusAttribute.cs": "*",
    }
    for name, capability in groups.items():
        path = root / name
        text = path.read_text(encoding="utf-8-sig")
        pattern = r"await (_?licenseService)\.HasActiveLicense\(([^)]*)\)"
        independent = "await Kavita.Common.IndependentProvider.Any()" if capability == "*" else f'await Kavita.Common.IndependentProvider.Has("{capability}")'
        text, count = re.subn(pattern, lambda m: "(Kavita.Common.IndependentProvider.Enabled ? " + independent + " : " + m[0] + ")", text)
        if not count:
            raise ValueError(f"Functional gate missing: {name}")
        text = re.sub(r'(?m)^(\s*)(\(Kavita.Common.IndependentProvider.Enabled[^\n]*\));$', r'\1_ = \2;', text)
        path.write_text(text)
    replace(root, "Kavita.Services/Plus/ScrobblingService.cs", "        if (string.IsNullOrEmpty(license.Value)) return true;", "        if (!Kavita.Common.IndependentProvider.Enabled && string.IsNullOrEmpty(license.Value)) return true;")
    scrobbling = "Kavita.Services/Plus/ScrobblingService.cs"
    replace(root, scrobbling, "            var scrobbleProvider = user.ScrobbleProviders[provider];", "            if (IndependentProvider.Enabled && !IndependentProvider.KnownScrobbleAction((int)provider, (int)eventType)) continue;\n            var scrobbleProvider = user.ScrobbleProviders[provider];")
    replace(root, scrobbling, "    private async Task<bool> CheckIfCannotScrobble(ScrobbleProvider provider, ScrobbleEventType eventType, int userId, int seriesId, Series series)\n    {", "    private async Task<bool> CheckIfCannotScrobble(ScrobbleProvider provider, ScrobbleEventType eventType, int userId, int seriesId, Series series)\n    {\n        if (IndependentProvider.Enabled && !IndependentProvider.KnownScrobbleAction((int)provider, (int)eventType)) return true;\n        if (IndependentProvider.Enabled && eventType == ScrobbleEventType.ChapterRead &&\n            (await _unitOfWork.SeriesRepository.GetSeriesDtoByIdAsync(seriesId, userId))?.TotalReads > 1) return true;")
    replace(root, scrobbling, "            if (!await ValidateUserToken(user, evt)) continue;", "            if (IndependentProvider.Enabled && !await IndependentProvider.ScrobbleAction((int)evt.ScrobbleProvider, (int)evt.ScrobbleEventType, ct)) continue;\n            if (!await ValidateUserToken(user, evt)) continue;")
    replace(root, scrobbling, "    public async Task<int> PostScrobbleUpdate(ScrobbleV3Dto data, string license, ScrobbleEvent evt)\n    {", "    public async Task<int> PostScrobbleUpdate(ScrobbleV3Dto data, string license, ScrobbleEvent evt)\n    {\n        if (IndependentProvider.Enabled) return await PostIndependentScrobbleUpdate(data, evt);")
    replace(root, scrobbling, "    private async Task CleanupOldOrBuggedEvents()\n    {", "    private async Task CleanupOldOrBuggedEvents()\n    {\n        // Independent events survive credential removal and can resume after reconnect.\n        if (IndependentProvider.Enabled) return;")
    # An independent delivery failure must never be converted into a permanent event error.
    replace(root, "Kavita.Services/Plus/KavitaPlusApiService.cs", "    public async Task<ScrobbleResponseDto> PostScrobbleV3UpdateAsync(ScrobbleV3Dto data, string license, CancellationToken ct = default)\n    {", "    public async Task<ScrobbleResponseDto> PostScrobbleV3UpdateAsync(ScrobbleV3Dto data, string license, CancellationToken ct = default)\n    {\n        if (IndependentProvider.Enabled)\n        {\n            try { return await (Configuration.KavitaPlusApiUrl + \"/api/v3/Scrobble\").WithKavitaPlusHeaders(\"\").PostJsonAsync(data, cancellationToken: ct).ReceiveJson<ScrobbleResponseDto>(); }\n            catch (Exception) { return new ScrobbleResponseDto { Successful = false, ErrorMessage = \"Independent delivery is unconfirmed\" }; }\n        }")
    for status, kind, fingerprint in (("onHoldStatus", "Inactive", "inactiveHash"), ("droppedStatus", "Dropped", "droppedHash")):
        call = f"await scrobbleProviderService.ScrobbleReadStatusUpdates(ctx, {status}, TransitionRuleKind.{kind}, {fingerprint}, ct);"
        replace(root, scrobbling, call, f"if (!IndependentProvider.Enabled || {status} is ScrobbleReadStatus.WantToRead or ScrobbleReadStatus.Read or ScrobbleReadStatus.Dropped or ScrobbleReadStatus.OnHold)\n                        " + call, count=2)
    path = root / scrobbling
    path.write_text(path.read_text().replace('await Kavita.Common.IndependentProvider.Has("scrobbling")', 'await Kavita.Common.IndependentProvider.CanQueueScrobbleEvents()'))
    # Avoid scheduling subscription info refreshes in independent mode.
    path = root / "Kavita.Services/TaskScheduler.cs"
    text = path.read_text()
    text = text.replace("    public async Task ScheduleKavitaPlusTasks(CancellationToken cancellationToken = default)\n    {", "    public async Task ScheduleKavitaPlusTasks(CancellationToken cancellationToken = default)\n    {\n        if (Kavita.Common.IndependentProvider.Enabled)\n        {\n            RemoveKavitaPlusTasks();\n            RecurringJob.RemoveIfExists(TaskSchedulerConstants.RefreshConnectedTokensId);\n        }")
    begin = text.index("        // Get the License Info")
    end = text.index("        // KavitaPlus Scrobbling", begin)
    text = text[:begin] + "        if (!Kavita.Common.IndependentProvider.Enabled)\n        {\n" + text[begin:end] + "        }\n\n" + text[end:]
    # Schedule only supported feature families. Remove persisted jobs for unavailable families.
    begin = text.index("    public async Task ScheduleKavitaPlusTasks(")
    end = text.index("\n    }", begin)
    schedule = text[begin:end]
    def schedule_gate(match):
        call = match[0]
        feature = next((feature for anchor, feature in (
            ("CheckExternalAccessTokens", "scrobbling"),
            ("ProcessUpdatesSinceLastSync", "scrobbling"),
            ("ClearProcessedEvents", "scrobbling"),
            ("_externalMetadataService", "metadata"),
            ("_smartCollectionSyncService", "stacks"),
            ("_wantToReadSyncService", "wantToRead"),
            ("CreateReadStatusTransitionRuleEventsId", "scrobbling"),
            ("RefreshConnectedTokensId", "oauth"),
        ) if anchor in call), None)
        if feature is None:
            return call
        guard = f'!Kavita.Common.IndependentProvider.Enabled || await Kavita.Common.IndependentProvider.Has("{feature}")'
        result = "        if (" + guard + ")\n        {\n" + call + "\n        }"
        if "RecurringJob.AddOrUpdate" in call:
            job = re.search(r"\(\s*([^,]+),", call)[1]
            result += "\n        else { RecurringJob.RemoveIfExists(" + job + "); }"
        return result
    schedule = re.sub(r"(?m)^        (?:RecurringJob\.AddOrUpdate(?:<[^>]+>)?|BackgroundJob\.Enqueue)\([\s\S]*?;", schedule_gate, schedule)
    text = text[:begin] + schedule + text[end:]
    path.write_text(text)
    controller = '''// Modified 2026-10-22. GPL-3.0.
using System.Threading.Tasks;
using Kavita.Common;
using Microsoft.AspNetCore.Mvc;
namespace Kavita.Server.Controllers;
public class ProviderCapabilitiesController : BaseApiController
{
    [HttpGet]
    public async Task<IActionResult> Get() => Ok(await IndependentProvider.Manifest(HttpContext.RequestAborted));
}
'''
    (root / "Kavita.Server/Controllers/ProviderCapabilitiesController.cs").write_text(controller)
    replace(root, "Kavita.Server/Controllers/OAuthController.cs", "    public async Task<IActionResult> StartFlow([FromQuery] OAuthUpstream upstream)\n    {",
            "    public async Task<IActionResult> StartFlow([FromQuery] OAuthUpstream upstream)\n    {\n        if (IndependentProvider.Enabled) return await StartIndependentFlow(upstream);")
    replace(root, "Kavita.Server/Controllers/OAuthController.cs", "        try\n        {\n            apiKey = _dataProtector.Unprotect(apiKey);", '        if (IndependentProvider.Enabled) return BadRequest("Use the independent OAuth callback.");\n        try\n        {\n            apiKey = _dataProtector.Unprotect(apiKey);')
    replace(root, "Kavita.Server/Controllers/OAuthController.cs", "    private static string GetInstanceUrl", (HERE / "OAuthController.methods.txt").read_text() + "    private static string GetInstanceUrl")
    # Independent tokens travel in POST bodies, never in URLs that exception logs may include.
    functional = "Kavita.Services/Plus/KavitaPlusApiService.cs"
    calls = [
        ("public async Task<KPlusResult<bool>> HasTokenExpiredForProviderAsync(ScrobbleProvider provider, string token, string license, CancellationToken ct = default)", "bool", "/api/v3/Scrobble/valid-access-token", "new { provider, accessToken = token }"),
        ("public async Task<KPlusResult<int>> GetRateLimitForProviderAsync(ScrobbleProvider provider, string token, string license, CancellationToken ct = default)", "int", "/api/v3/Scrobble/rate-limit", "new { provider, accessToken = token }"),
        ("public async Task<KPlusResult<List<ExternalSeriesDetailDto>>> GetWantToRead(ScrobbleProvider provider, string token,\n        string license, CancellationToken ct = default)", "List<ExternalSeriesDetailDto>", "/api/v3/Scrobble/want-to-read", "new { provider, accessToken = token }"),
        ("public async Task<KPlusResult<KavitaPlusUserInfo>> GetUserInfo(ScrobbleProvider provider, string token, string license, CancellationToken ct = default)", "KavitaPlusUserInfo", "/api/v3/Scrobble/user-info", "new { provider, accessToken = token }"),
        ("public async Task<KPlusResult<DateTime>> GetTokenExpiry(OAuthUpstream upstream, string accessToken, CancellationToken ct = default)", "DateTime", "/api/v3/oauth/token-expiration", "new { upstream, accessToken }"),
    ]
    for signature, result_type, route, payload in calls:
        replace(root, functional, signature + "\n    {", signature + "\n    {\n        if (IndependentProvider.Enabled) return await IndependentRequest<" + result_type + ">(" + repr(route).replace("'", '\"') + ", " + payload + ", ct);")
    replace(root, functional, "    public async Task<int> GetRateLimitAsync(string license, string token, CancellationToken ct = default)\n    {", '    public async Task<int> GetRateLimitAsync(string license, string token, CancellationToken ct = default)\n    {\n        if (IndependentProvider.Enabled) throw new InvalidOperationException("Legacy scrobbling protocol unavailable in independent mode");')
    replace(root, functional, '    private const string ScrobblingPath', '''    private async Task<KPlusResult<T>> IndependentRequest<T>(string path, object payload, CancellationToken ct)
    {
        try
        {
            return await (Configuration.KavitaPlusApiUrl + path).WithKavitaPlusHeaders("")
                .PostJsonAsync(payload, cancellationToken: ct).ReceiveJson<KPlusResult<T>>();
        }
        catch (Exception)
        {
            logger.LogWarning("Independent provider request failed for {Path}", path);
            return KPlusResult<T>.Failure("Independent provider request failed; check provider availability and configuration.");
        }
    }
    private const string ScrobblingPath''')
    for provider in ("MangaBaka", "Mal"):
        old = f"await SetScrobbleProviderToken(user, ScrobbleProvider.{provider}, token, refreshToken);"
        replace(root, "Kavita.Services/Plus/OAuthService.cs", old, f"await SetScrobbleProviderToken(user, ScrobbleProvider.{provider}, token, refreshToken, Kavita.Common.IndependentProvider.Enabled ? expiresIn : null);")
    replace(root, "Kavita.Services/Plus/OAuthService.cs", "await SetScrobbleProviderToken(user, ScrobbleProvider.AniList, token);", "await SetScrobbleProviderToken(user, ScrobbleProvider.AniList, token, null, Kavita.Common.IndependentProvider.Enabled ? expiresIn : null);")
    # Opaque OAuth/PAT tokens must not be parsed as JWTs or assigned invented expiry dates.
    scrobbling = "Kavita.Services/Plus/ScrobblingService.cs"
    replace(root, scrobbling, "    private async Task<DateTime?> GetTokenExpiry(ScrobbleProvider provider, int userId, string token, CancellationToken ct = default)\n    {", "    private async Task<DateTime?> GetTokenExpiry(ScrobbleProvider provider, int userId, string token, CancellationToken ct = default)\n    {\n        if (IndependentProvider.Enabled)\n        {\n            var independentUpstream = provider.ToOAuthUpstream();\n            return independentUpstream.HasValue ? await IndependentProvider.KnownTokenExpiry((int)independentUpstream.Value, token, ct) : null;\n        }")
    replace(root, scrobbling, "    private async Task<bool> HasTokenExpired(string token, ScrobbleProvider provider)\n    {", '    private async Task<bool> HasTokenExpired(string token, ScrobbleProvider provider)\n    {\n        if (IndependentProvider.Enabled)\n        {\n            var independentValidity = await _kavitaPlusApiService.HasTokenExpiredForProviderAsync(provider, token, string.Empty);\n            if (!independentValidity.IsSuccess) throw new KavitaException("Independent token validity is unknown; retry provider validation.");\n            return independentValidity.Data;\n        }')
    replace(root, scrobbling, "    private async Task<bool> ValidateUserToken(AppUser user, ScrobbleEvent evt)\n    {", "    private async Task<bool> ValidateUserToken(AppUser user, ScrobbleEvent evt)\n    {\n        if (IndependentProvider.Enabled) return await ValidateIndependentAccount(evt.ScrobbleProvider, user.ScrobbleProviders[evt.ScrobbleProvider].AuthenticationToken);")
    replace(root, scrobbling, "    public async Task CheckExternalAccessTokens(CancellationToken ct = default)\n    {", "    public async Task CheckExternalAccessTokens(CancellationToken ct = default)\n    {\n        if (IndependentProvider.Enabled)\n        {\n            await CheckIndependentAccessTokens(ct);\n            return;\n        }")
    replace(root, scrobbling, "    private async Task<DateTime?> GetTokenExpiry(", (HERE / "ScrobblingService.independent.txt").read_text() + "    private async Task<DateTime?> GetTokenExpiry(")
    replace(root, scrobbling, "        // Hardcover is not JWT and has no introspection. However, the validity is in callback\n        if (provider is not ScrobbleProvider.Hardcover)", "        if (IndependentProvider.Enabled)\n        {\n            // Unknown expiry is not evidence that an authenticated PAT is expired. Preserve stored state.\n            if (!userInfo.IsSuccess || userInfo.Data == null) return;\n            var actualExpiry = await GetTokenExpiry(provider, userId, scrobbleProviderSettings.AuthenticationToken, ct);\n            if (actualExpiry.HasValue) scrobbleProviderSettings.ValidUntilUtc = actualExpiry.Value;\n        }\n        // Official-mode behavior remains unchanged.\n        else if (provider is not ScrobbleProvider.Hardcover)")
    replace(root, "Kavita.Services/Plus/OAuthService.cs", "        var timeRemaining = settings.ValidUntilUtc - DateTime.UtcNow;", "        var timeRemaining = settings.ValidUntilUtc - DateTime.UtcNow;\n        if (Kavita.Common.IndependentProvider.Enabled)\n        {\n            var actualExpiry = await Kavita.Common.IndependentProvider.KnownTokenExpiry((int)upstream.Value, settings.AuthenticationToken, ct);\n            if (!actualExpiry.HasValue) return; // No expiry is invented for legacy PATs.\n            timeRemaining = actualExpiry.Value - DateTime.UtcNow;\n        }")
    replace(root, "Kavita.Services/Plus/OAuthService.cs", "        user.ScrobbleProviders[provider].ValidUntilUtc = expiresIn.HasValue\n            ? DateTime.UtcNow + TimeSpan.FromSeconds(expiresIn.Value) - TimeSpan.FromSeconds(30)\n            : DateTime.MaxValue;", "        if (expiresIn.HasValue)\n            user.ScrobbleProviders[provider].ValidUntilUtc = DateTime.UtcNow + TimeSpan.FromSeconds(expiresIn.Value) - TimeSpan.FromSeconds(30);\n        else if (!Kavita.Common.IndependentProvider.Enabled)\n            user.ScrobbleProviders[provider].ValidUntilUtc = DateTime.MaxValue;")
    controller = "Kavita.Server/Controllers/ScrobblingController.cs"
    replace(root, controller, "        if (string.IsNullOrEmpty(dto.AuthenticationToken))", "        // Clearing independent credentials pauses delivery and keeps pending events/rules.\n        if (Kavita.Common.IndependentProvider.Enabled && string.IsNullOrEmpty(scrobbleProvider.AuthenticationToken))\n        {\n            await scrobblingService.SyncProviderInfo(UserId, dto.Provider, HttpContext.RequestAborted);\n            return Ok();\n        }\n\n        if (string.IsNullOrEmpty(dto.AuthenticationToken))")
    replace(root, controller, '        if (scrobbleProvider.AuthenticationToken.StartsWith("hc_at") && !hadAuthToken &&', '        if (!Kavita.Common.IndependentProvider.Enabled && scrobbleProvider.AuthenticationToken.StartsWith("hc_at") && !hadAuthToken &&')
    for dto in ("Kavita.Models/DTOs/KavitaPlus/Scrobble/ScrobbleProviderDto.cs", "Kavita.Models/DTOs/KavitaPlus/Account/UserTokenInfoDto.cs"):
        replace(root, dto, "    public DateTime ValidUntilUtc { get; set; }", "    public DateTime ValidUntilUtc { get; set; }\n    public bool? TokenExpiryKnown { get; set; }")
    replace(root, controller, "        return Ok(providers);", '''        if (Kavita.Common.IndependentProvider.Enabled)
        {
            foreach (var item in providers)
            {
                if (string.IsNullOrEmpty(item.AuthenticationToken)) continue;
                var upstream = Kavita.Common.IndependentProvider.OAuthUpstreamFor((int)item.Provider);
                var actualExpiry = upstream.HasValue ? await Kavita.Common.IndependentProvider.KnownTokenExpiry(upstream.Value, item.AuthenticationToken, HttpContext.RequestAborted) : null;
                item.TokenExpiryKnown = actualExpiry.HasValue;
                if (actualExpiry.HasValue) item.ValidUntilUtc = actualExpiry.Value;
            }
        }
        return Ok(providers);''')
    replace(root, scrobbling, "        return users.Select(user => new UserTokenInfoDto", "        var tokenInfos = users.Select(user => new UserTokenInfoDto")
    replace(root, scrobbling, "        }).ToList();\n    }\n\n    #region Access token checks", '''        }).ToList();
        if (IndependentProvider.Enabled)
        {
            foreach (var item in tokenInfos)
            {
                var user = users.First(user => user.Id == item.UserId);
                foreach (var info in item.Tokens)
                {
                    var token = user.ScrobbleProviders[info.Provider].AuthenticationToken;
                    if (string.IsNullOrEmpty(token)) continue;
                    var upstream = info.Provider.ToOAuthUpstream();
                    var actualExpiry = upstream.HasValue ? await IndependentProvider.KnownTokenExpiry((int)upstream.Value, token, ct) : null;
                    info.TokenExpiryKnown = actualExpiry.HasValue;
                    if (actualExpiry.HasValue) info.ValidUntilUtc = actualExpiry.Value;
                }
            }
        }
        return tokenInfos;
    }

    #region Access token checks''')
    for model in ("UI/Web/src/app/_models/kavitaplus/scrobble-providers/user-scrobble-provider.ts", "UI/Web/src/app/_models/kavitaplus/user-token-info.ts"):
        marker = "  validUntilUtc!: string;" if "scrobble-providers/" in model else "  validUntilUtc: string;"
        replace(root, model, marker, marker + "\n  tokenExpiryKnown?: boolean;")
    template = "UI/Web/src/app/user-settings/manage-scrobble-providers/manage-scrobble-providers.component.html"
    old = '<span [ngbTooltip]="userScrobbleProvider.validUntilUtc | utcToLocalTime">{{ t(\'expires\', {time: userScrobbleProvider.validUntilUtc | utcToLocalDate | timeDifference}) }}</span>'
    replace(root, template, old, '@if (userScrobbleProvider.tokenExpiryKnown === false) { <span>Expiry unknown; account checked when used.</span> } @else { ' + old + ' }')
    template = "UI/Web/src/app/user-settings/_modals/manage-user-scrobble-provider-modal/manage-user-scrobble-provider-modal.component.html"
    old = '<dd [ngbTooltip]="userScrobbleProvider().validUntilUtc | utcToLocalTime">{{ userScrobbleProvider().validUntilUtc | utcToLocalDate | timeDifference | defaultValue }}</dd>'
    replace(root, template, old, '@if (userScrobbleProvider().tokenExpiryKnown === false) { <dd>Expiry unknown; account checked when used.</dd> } @else { ' + old + ' }')
    replace(root, "UI/Web/src/app/user-settings/scrobble-account-card/scrobble-account-card.component.ts", "  hasExpired = computed(() => {", "  hasExpired = computed(() => {\n    if (this.provider().tokenExpiryKnown === false) return false;")
    replace(root, "UI/Web/src/app/user-settings/scrobble-account-card/scrobble-account-card.component.html", '        <div class="small text-muted text-truncate">{{username() ? username() : \'\'}}</div>', '        <div class="small text-muted text-truncate">{{username() ? username() : \'\'}}</div>\n        @if (provider().tokenExpiryKnown === false) { <div class="small text-muted">Expiry unknown; account checked when used.</div> }')
    template = "UI/Web/src/app/admin/manage-user-tokens/manage-user-tokens.component.html"
    replace(root, template, "@if (info && info.validUntilUtc !== NULL_DATE)", "@if (info?.tokenExpiryKnown === false) { <span>Expiry unknown</span> } @else if (info && info.validUntilUtc !== NULL_DATE)")
    replace(root, template, "@if (info && info.validUntilUtc != NULL_DATE)", "@if (info?.tokenExpiryKnown === false) { <span>Expiry unknown</span> } @else if (info && info.validUntilUtc != NULL_DATE)")
    want_to_read = "Kavita.Services/Plus/WantToReadSyncService.cs"
    replace(root, want_to_read, "using Flurl.Http;", "using Flurl.Http;\nusing Microsoft.EntityFrameworkCore;\nusing Kavita.Models.Extensions;")
    replace(root, want_to_read, "    public async Task Sync(CancellationToken ct = default)", (HERE / "WantToReadSyncService.independent.txt").read_text() + "    public async Task Sync(CancellationToken ct = default)")
    replace(root, want_to_read, "                externalSeries.AddRange(result.Data ?? []);", '''                if (IndependentProvider.Enabled && (result.Data ?? []).Any(item => item.Provider != kv.Key || !IndependentWantToReadMatcher.Identity(item).HasValue))
                {
                    logger.LogWarning("Independent want-to-read returned missing or mismatched provider identities for {Provider}; no entries imported", kv.Key);
                    continue;
                }
                externalSeries.AddRange(result.Data ?? []);''')
    replace(root, want_to_read, "                var match = await unitOfWork.SeriesRepository.MatchSeriesAsync(unmatchedSeries, ct);", "                var match = IndependentProvider.Enabled\n                    ? await MatchIndependentSeries(unmatchedSeries, user, ct)\n                    : await unitOfWork.SeriesRepository.MatchSeriesAsync(unmatchedSeries, ct);")
    service = "UI/Web/src/app/_services/license.service.ts"
    replace(root, service, "  private readonly baseUrl = environment.apiUrl;", '''  private readonly baseUrl = environment.apiUrl;
  readonly independent = signal(false);
  readonly providerLimitations = signal<string[]>([]);
  private readonly providerCapabilities = signal<string[]>([]);
  private readonly personalActions = signal<Record<number, string[]>>({});
  supportsScrobbleAction(provider: number, event: number): boolean {
    return !this.independent() || supportsSyncAction(this.personalActions(), provider, event);
  }
  supportsReviewVisibility(provider: number, visibility: number): boolean {
    return !this.independent() || visibility !== 1 || (this.personalActions()[provider] ?? []).includes('friendsOnlyReviews');
  }
  hasFeature(capability: string): boolean {
    return this.independent() ? this.providerCapabilities().includes(capability) : this.hasActiveLicense();
  }
  hasFeatureAccess(): boolean {
    return this.independent() ? this.providerCapabilities().length > 0 : this.hasActiveLicense();
  }
  constructor() { this.refreshProviderCapabilities(); }
  private refreshProviderCapabilities() {
    this.httpClient.get<{mode: string; providers: IndependentCapability[]; limitations: string[]}>(
      this.baseUrl + 'providercapabilities').subscribe({
        next: manifest => {
          this.personalActions.set(personalSyncActions(manifest.providers));
          this.independent.set(manifest.mode === 'independent');
          this.providerCapabilities.set(manifest.providers.filter(p => p.available).flatMap(p => p.capabilities));
          this.providerLimitations.set(manifest.limitations);
        },
        error: () => { this.personalActions.set({}); this.providerCapabilities.set([]); this.providerLimitations.set(['Provider capability status is unavailable.']); }
      });
  }''')
    replace(root, service, "  checkForValidLicense(forceCheck: boolean = false) {", "  checkForValidLicense(forceCheck: boolean = false) {\n    this.refreshProviderCapabilities();")
    app = root / "UI/Web/src/app"
    for path in app.rglob("*"):
        if path.suffix not in (".ts", ".html") or path == root / service or "/admin/kavita-plus/" in str(path):
            continue
        text = path.read_text()
        # Subscription/donation display stays truthful. Functional nav and settings use separate state.
        if path.name in ("side-nav.component.html", "preference-nav.component.html"):
            continue
        if "licenseService.hasActiveLicense" in text:
            feature = "scrobbling" if "/profile/" in str(path) else "metadata" if any(s in str(path) for s in ("cover-chooser", "person-detail", "manage-metadata", "manage-public-metadata")) else None
            replacement = f"licenseService.hasFeature('{feature}')" if feature else "licenseService.hasFeatureAccess()"
            text = text.replace("licenseService.hasActiveLicense()", replacement)
            text = text.replace("toObservable(this.licenseService.hasActiveLicense)", "toObservable(computed(() => this.licenseService.hasFeatureAccess()))")
            # Avoid requiring another Angular import for nav observable.
            text = text.replace("toObservable(computed(() => this.licenseService.hasFeatureAccess()))", "toObservable(this.licenseService.providerAccess)")
            path.write_text(text)
    replace(root, service, "inject, Injectable, signal", "computed, inject, Injectable, signal")
    replace(root, service, "  readonly independent = signal(false);", "  readonly independent = signal(false);\n  readonly providerAccess = computed(() => this.hasFeatureAccess());")
    license_path = root / service
    license_path.write_text('import {IndependentCapability, personalSyncActions, supportsSyncAction} from "./independent-actions";\n' + license_path.read_text())
    settings_ts = "UI/Web/src/app/user-settings/manage-scrobble-providers/manage-scrobble-providers.component.ts"
    replace(root, settings_ts, "export class ManageScrobbleProvidersComponent implements OnInit {", "export class ManageScrobbleProvidersComponent implements OnInit {\n  protected readonly independentLicense = inject(LicenseService);")
    path = root / settings_ts
    path.write_text('import {LicenseService} from "../../_services/license.service";\n' + path.read_text())
    settings_html = root / "UI/Web/src/app/user-settings/manage-scrobble-providers/manage-scrobble-providers.component.html"
    text = settings_html.read_text()
    for event in ("ChapterRead", "ScoreUpdated", "AddWantToRead", "Review"):
        old = f"ProviderSupportedEvents[provider].includes(ScrobbleEventType.{event})"
        text = text.replace(old, old + f" && independentLicense.supportsScrobbleAction(provider, ScrobbleEventType.{event})")
    rule_gate = "ProviderSupportedEvents[provider].includes(ScrobbleEventType.ChapterRead) && independentLicense.supportsScrobbleAction(provider, ScrobbleEventType.ChapterRead)"
    before, after = text.rsplit(rule_gate, 1)
    text = before + rule_gate.replace("supportsScrobbleAction(provider, ScrobbleEventType.ChapterRead)", "supportsScrobbleAction(provider, ScrobbleEventType.ReadStatusUpdate)") + after
    text = text.replace('<option [ngValue]="opt">{{opt | reviewScrobbleTargetName}}</option>', '<option [ngValue]="opt" [disabled]="!independentLicense.supportsReviewVisibility(provider, opt)">{{opt | reviewScrobbleTargetName}}</option>')
    text = text.replace('<option [ngValue]="opt">{{ opt | scrobbleReadStatus }}</option>', '<option [ngValue]="opt" [disabled]="independentLicense.independent() && opt === 3">{{ opt | scrobbleReadStatus }}</option>')
    text = text.replace("{{ t('sync-options') }}", "{{ t('sync-options') }}\n                @if (independentLicense.independent()) { <div class=\"form-text\">Only supported actions for this provider are shown. Rereads and unread resets are held until supported.</div> }")
    settings_html.write_text(text)
    replace(root, settings_ts, "  protected readonly ProviderSupportedEvents = ProviderSupportedEvents;", "  protected readonly ProviderSupportedEvents = ProviderSupportedEvents;")
    # The title remains subscription-specific; status makes independent capabilities and gaps visible.
    template = "UI/Web/src/app/settings/_components/settings/settings.component.html"
    replace(root, template, '<div class="main-container container-fluid">', '''<div class="main-container container-fluid">
  @if (licenseService.independent()) {
    <div class="alert alert-info" role="status">
      Independent provider services. No paid Kavita+ subscription is claimed.
      @for (limitation of licenseService.providerLimitations(); track $index) { <p>{{limitation}}</p> }
    </div>
  }''')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    patch(args.source.resolve())
