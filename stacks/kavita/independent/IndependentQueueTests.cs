// Isolated acceptance fixture for the actual pinned native queue. GPL-3.0.
using System.Net.Http.Json;
using System.Text.Json;
using AutoMapper;
using Kavita.API.Database;
using Kavita.API.Store;
using Kavita.API.Services;
using Kavita.API.Services.Plus;
using Kavita.API.Services.SignalR;
using Kavita.Common;
using Kavita.Database;
using Kavita.Database.Tests;
using Kavita.Models.DTOs.KavitaPlus.Scrobble;
using Kavita.Models.DTOs.KavitaPlus.ExternalMetadata;
using Kavita.Models.Entities.Enums;
using Kavita.Models.Entities.Enums.KavitaPlus;
using Kavita.Models.Entities.Enums.UserPreferences;
using Kavita.Services.Plus;
using Kavita.Services.Plus.ScrobbleService;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using Xunit.Abstractions;

namespace Kavita.Services.Tests;

public class IndependentQueueTests(ITestOutputHelper output) : AbstractDbTest(output)
{
    private async Task<int> Control(string mode)
    {
        using var client = new HttpClient();
        client.DefaultRequestHeaders.Add("X-Provider-Key", "native-fixture-key-123456789012345678901234");
        using var body = new StringContent(JsonSerializer.Serialize(new { mode }), System.Text.Encoding.UTF8, "application/json");
        using var response = await client.PostAsync(Environment.GetEnvironmentVariable("KAVITA_QUEUE_CONTROL"), body);
        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<JsonElement>();
        if (mode == "status") output.WriteLine(result.ToString());
        return result.GetProperty("mutations").GetInt32();
    }

    private static ScrobblingService NativeService(IUnitOfWork unit, IEventHub? events = null)
    {
        var audit = Substitute.For<IKavitaPlusAuditService>();
        var collection = new ServiceCollection();
        collection.AddKeyedScoped<IScrobbleProviderService>(ScrobbleProvider.AniList, (_, _) => new AniListScrobbleProviderService(NullLogger<AniListScrobbleProviderService>.Instance, unit, audit));
        collection.AddKeyedScoped<IScrobbleProviderService>(ScrobbleProvider.Mal, (_, _) => new MyAnimeListScrobbleProviderService(NullLogger<MyAnimeListScrobbleProviderService>.Instance, unit, audit));
        collection.AddKeyedScoped<IScrobbleProviderService>(ScrobbleProvider.MangaBaka, (_, _) => new MangabakaScrobbleProviderService(NullLogger<MangabakaScrobbleProviderService>.Instance, unit, audit));
        collection.AddKeyedScoped<IScrobbleProviderService>(ScrobbleProvider.Hardcover, (_, _) => new HardcoverScrobbleProviderService(NullLogger<HardcoverScrobbleProviderService>.Instance, unit, audit));
        var api = new KavitaPlusApiService(NullLogger<KavitaPlusApiService>.Instance, unit, new EphemeralDataProtectionProvider());
        return new ScrobblingService(unit, events ?? Substitute.For<IEventHub>(), NullLogger<ScrobblingService>.Instance,
            Substitute.For<ILicenseService>(), Substitute.For<ILocalizationService>(), Substitute.For<IEmailService>(),
            api, collection.BuildServiceProvider(), audit, new ScrobbleRuleService(unit, NullLogger<ScrobbleRuleService>.Instance));
    }

    private async Task<(string, IMapper)> SeedQueue(bool reset = false, bool outage = false, bool cold = false)
    {
        await Control("reset");
        var (unit, context, mapper) = await CreateDatabase();
        await using var helper = new ScrobblingServiceTests(output);
        await helper.Setup(unit, context);
        var native = NativeService(unit);
        if (outage)
        {
            ExpireManifest();
            await IndependentProvider.Manifest();
            await Control("manifest-down");
            if (cold) typeof(IndependentProvider).GetField("Actions", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static)!.SetValue(null, null);
            ExpireManifest();
        }
        await native.ScrobbleSeriesRatingUpdate(1, 1, 4);
        var events = await unit.ScrobbleRepository.GetAllEventsForSeries(1);
        Assert.Single(events);
        if (reset)
        {
            events[0].ScrobbleEventType = ScrobbleEventType.ReadStatusUpdate;
            events[0].ReadStatus = ScrobbleReadStatus.UnRead;
            unit.ScrobbleRepository.Update(events[0]);
            await unit.CommitAsync();
        }
        var path = Path.Combine(Path.GetTempPath(), "kavita-native-queue-" + Guid.NewGuid() + ".sqlite3");
        using var dest = new SqliteConnection("Data Source=" + path);
        dest.Open();
        ((SqliteConnection)context.Database.GetDbConnection()).BackupDatabase(dest);
        return (path, mapper);
    }

    private async Task Cycle(string path, IMapper mapper, bool processed)
    {
        // Reopen SQLite and reconstruct the native service each cycle.
        await using var context = new DataContext(new DbContextOptionsBuilder<DataContext>().UseSqlite("Data Source=" + path).Options);
        var unit = new UnitOfWork(context, mapper, null!);
        await NativeService(unit).ProcessUpdatesSinceLastSync();
        context.ChangeTracker.Clear();
        var events = await unit.ScrobbleRepository.GetAllEventsForSeries(1);
        Assert.Single(events);
        if (processed != events[0].IsProcessed) await Control("status");
        Assert.Equal(processed, events[0].IsProcessed);
        Assert.False(events[0].IsErrored);
    }

    [Theory]
    [InlineData("down")]
    [InlineData("ambiguous")]
    [InlineData("expired")]
    [InlineData("rate")]
    [InlineData("blank")]
    [InlineData("graphql-rate")]
    public async Task Native_FailuresRetainQueueAndRecoverAfterGatewayRestart(string failure)
    {
        var (path, mapper) = await SeedQueue();
        try
        {
            await Control(failure);
            await Cycle(path, mapper, false);
            if (failure is "rate" or "graphql-rate")
            {
                await Control("normal"); // actual process restart, persisted cooldown remains
                await Cycle(path, mapper, false);
                Assert.Equal(0, await Control("expire-cooldown"));
            }
            else
            {
                var mutations = await Control("normal");
                Assert.Equal(failure == "ambiguous" ? 1 : 0, mutations);
            }
            await Cycle(path, mapper, true);
            Assert.Equal(1, await Control("restart"));
            await Cycle(path, mapper, true);
            Assert.Equal(1, await Control("restart"));
        }
        finally { File.Delete(path); File.Delete(path + "-wal"); File.Delete(path + "-shm"); }
    }

    [Fact]
    public async Task Native_UnreadResetIsHeldWithoutPermanentErrorOrWrite()
    {
        var (path, mapper) = await SeedQueue(true);
        try
        {
            await Cycle(path, mapper, false);
            Assert.Equal(0, await Control("restart"));
        }
        finally { File.Delete(path); File.Delete(path + "-wal"); File.Delete(path + "-shm"); }
    }
    [Fact]
    public async Task Native_UnsupportedReviewDoesNotCreateAnEventOrChangeSettings()
    {
        await Control("reset");
        var (unit, context, _) = await CreateDatabase();
        await using var helper = new ScrobblingServiceTests(output);
        await helper.Setup(unit, context);
        var user = (await unit.UserRepository.GetUserByIdAsync(1))!;
        user.ScrobbleProviders[ScrobbleProvider.AniList].Settings.ReviewsScrobbling = false;
        user.ScrobbleProviders[ScrobbleProvider.MangaBaka].AuthenticationToken = "fixture-mangabaka-token";
        user.ScrobbleProviders[ScrobbleProvider.MangaBaka].Settings.ReviewsScrobbling = true;
        user.ScrobbleProviders[ScrobbleProvider.MangaBaka].Settings.AllLibraries = true;
        unit.UserRepository.Update(user);
        var series = (await unit.SeriesRepository.GetSeriesByIdAsync(1))!;
        series.MangaBakaId = 8;
        await unit.CommitAsync();
        await NativeService(unit).ScrobbleSeriesReviewUpdate(1, 1, "Fixture review title", "Fixture review body");
        Assert.Empty(await unit.ScrobbleRepository.GetAllEventsForSeries(1));
        Assert.True(user.ScrobbleProviders[ScrobbleProvider.MangaBaka].Settings.ReviewsScrobbling);
        Assert.Equal(0, await Control("restart"));
    }

    [Fact]
    public async Task Native_RereadPayloadIsHeldBeforeDelivery()
    {
        var (path, mapper) = await SeedQueue();
        try
        {
            await using var context = new DataContext(new DbContextOptionsBuilder<DataContext>().UseSqlite("Data Source=" + path).Options);
            var unit = new UnitOfWork(context, mapper, null!);
            var evt = (await unit.ScrobbleRepository.GetAllEventsForSeries(1)).Single();
            await Assert.ThrowsAsync<KavitaException>(() => NativeService(unit).PostScrobbleUpdate(new ScrobbleV3Dto {
                Provider = ScrobbleProvider.AniList, AuthenticationToken = "fixture-token", SeriesName = "Fixture series",
                Format = PlusMediaFormat.Manga, ScrobbleEventType = ScrobbleEventType.ChapterRead,
                AniListId = 39115, ChapterNumber = 3, TotalReadCountForSeries = 2
            }, "", evt));
            Assert.False(evt.IsProcessed);
            Assert.False(evt.IsErrored);
            Assert.Equal(0, await Control("restart"));
        }
        finally { File.Delete(path); File.Delete(path + "-wal"); File.Delete(path + "-shm"); }
    }

    [Fact]
    public async Task Native_MetadataDtoUsesTheGatewayJsonContract()
    {
        await Control("reset");
        var (unit, _, _) = await CreateDatabase();
        var api = new KavitaPlusApiService(NullLogger<KavitaPlusApiService>.Instance, unit, new EphemeralDataProtectionProvider());
        var result = await api.MatchSeriesV3Async(new MatchRequestV3Dto {
            Provider = MetadataProvider.Mangabaka, SeriesName = "Fixture title", Format = PlusMediaFormat.Manga
        });
        Assert.True(result.IsSuccess);
        Assert.NotNull(result.Data);
        Assert.Empty(result.Data);
        Assert.Equal(0, await Control("restart"));
    }

    private static void ExpireManifest() => typeof(IndependentProvider)
        .GetField("Expires", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static)!
        .SetValue(null, DateTime.MinValue);

    [Fact]
    public async Task Native_EventCreationSurvivesTemporaryGatewayOutage()
    {
        var (path, mapper) = await SeedQueue(outage: true);
        try
        {
            await Cycle(path, mapper, false);
            Assert.Equal(0, await Control("normal"));
            ExpireManifest();
            await Cycle(path, mapper, true);
            Assert.Equal(1, await Control("restart"));
        }
        finally { File.Delete(path); File.Delete(path + "-wal"); File.Delete(path + "-shm"); }
    }

    [Fact]
    public async Task Native_ColdRestartCreatesAndRecoversDuringGatewayOutage()
    {
        var (path, mapper) = await SeedQueue(outage: true, cold: true);
        try
        {
            await Cycle(path, mapper, false);
            Assert.Equal(0, await Control("normal"));
            ExpireManifest();
            await Cycle(path, mapper, true);
            Assert.Equal(1, await Control("restart"));
        }
        finally { File.Delete(path); File.Delete(path + "-wal"); File.Delete(path + "-shm"); }
    }

    [Fact]
    public async Task Native_ClearedCredentialRetainsPendingEventUntilReconnect()
    {
        var (path, mapper) = await SeedQueue();
        try
        {
            string token;
            await using (var context = new DataContext(new DbContextOptionsBuilder<DataContext>().UseSqlite("Data Source=" + path).Options))
            {
                var unit = new UnitOfWork(context, mapper, null!);
                var user = (await unit.UserRepository.GetUserByIdAsync(1))!;
                token = user.ScrobbleProviders[ScrobbleProvider.AniList].AuthenticationToken;
                user.ScrobbleProviders[ScrobbleProvider.AniList].UserName = "Fixture connected name";
                var userContext = Substitute.For<IUserContext>();
                userContext.GetUserIdOrThrow().Returns(1);
                var notifications = Substitute.For<IEventHub>();
                var controller = new Kavita.Server.Controllers.ScrobblingController(unit, NativeService(unit, notifications),
                    Substitute.For<IScrobbleRuleService>(), NullLogger<Kavita.Server.Controllers.ScrobblingController>.Instance,
                    Substitute.For<ILocalizationService>(), Substitute.For<IKavitaPlusAuditService>(), mapper);
                controller.ControllerContext = new Microsoft.AspNetCore.Mvc.ControllerContext {
                    HttpContext = new Microsoft.AspNetCore.Http.DefaultHttpContext {
                        RequestServices = new ServiceCollection().AddSingleton(userContext).BuildServiceProvider()
                    }
                };
                var result = await controller.UpdateUserScrobbleProvider(new UpdateScrobbleProviderDto {
                    Provider = ScrobbleProvider.AniList, AuthenticationToken = "", RefreshToken = ""
                });
                Assert.IsType<Microsoft.AspNetCore.Mvc.OkResult>(result);
                Assert.Equal("", user.ScrobbleProviders[ScrobbleProvider.AniList].AuthenticationToken);
                Assert.Equal("", user.ScrobbleProviders[ScrobbleProvider.AniList].UserName);
                await notifications.Received(1).SendMessageToAsync(Arg.Any<string>(),
                    Arg.Any<Kavita.Models.DTOs.SignalR.SignalRMessage>(), 1, Arg.Any<CancellationToken>());
            }
            await Cycle(path, mapper, false);
            Assert.Equal(0, await Control("status"));
            await using (var context = new DataContext(new DbContextOptionsBuilder<DataContext>().UseSqlite("Data Source=" + path).Options))
            {
                var unit = new UnitOfWork(context, mapper, null!);
                var user = (await unit.UserRepository.GetUserByIdAsync(1))!;
                user.ScrobbleProviders[ScrobbleProvider.AniList].AuthenticationToken = token;
                unit.UserRepository.Update(user);
                await unit.CommitAsync();
            }
            await Cycle(path, mapper, true);
            Assert.Equal(1, await Control("restart"));
            await Cycle(path, mapper, true);
            Assert.Equal(1, await Control("status"));
        }
        finally { File.Delete(path); File.Delete(path + "-wal"); File.Delete(path + "-shm"); }
    }

}
