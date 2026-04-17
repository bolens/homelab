import type { QueryInterface } from 'sequelize';
import { DataTypes } from 'sequelize';

/**
 * Single baseline migration (squashed): Sequelize `sync()` for all registered models, helper rollup
 * tables, then workspace backfill (`polar_webhook_deliveries`, Polar + billing on `users`, `votes.trustRiskScore`,
 * `workspaces` / `polls.workspace_id` are all owned by model definitions + sync — see `migrate.ts` imports).
 */
export async function up(queryInterface: QueryInterface): Promise<void> {
  await queryInterface.sequelize.sync();
  // Raw-SQL helper table used by pollPhaseHistory is not created by sequelize.sync().
  await queryInterface.createTable('poll_phase_events', {
    id: {
      type: DataTypes.BIGINT,
      autoIncrement: true,
      primaryKey: true,
    },
    pollId: {
      type: DataTypes.STRING(64),
      allowNull: false,
    },
    fromPhase: {
      type: DataTypes.STRING(32),
      allowNull: true,
    },
    toPhase: {
      type: DataTypes.STRING(32),
      allowNull: false,
    },
    actorType: {
      type: DataTypes.STRING(32),
      allowNull: false,
    },
    actorUserId: {
      type: DataTypes.INTEGER,
      allowNull: true,
    },
    source: {
      type: DataTypes.STRING(64),
      allowNull: false,
    },
    createdAt: {
      type: DataTypes.DATE,
      allowNull: false,
      defaultValue: DataTypes.NOW,
    },
  });
  await queryInterface.addIndex('poll_phase_events', ['pollId', 'createdAt'], {
    name: 'poll_phase_events_poll_created_idx',
  });

  await queryInterface.createTable('poll_vote_rollups', {
    poll_id: {
      type: DataTypes.STRING(64),
      allowNull: false,
      primaryKey: true,
    },
    total_votes: {
      type: DataTypes.INTEGER,
      allowNull: false,
      defaultValue: 0,
    },
    votes_last_1m: {
      type: DataTypes.INTEGER,
      allowNull: false,
      defaultValue: 0,
    },
    votes_last_24h: {
      type: DataTypes.INTEGER,
      allowNull: false,
      defaultValue: 0,
    },
    quarantined_votes_pending: {
      type: DataTypes.INTEGER,
      allowNull: false,
      defaultValue: 0,
    },
    updated_at: {
      type: DataTypes.DATE,
      allowNull: false,
      defaultValue: DataTypes.NOW,
    },
  });
  await queryInterface.addIndex('poll_vote_rollups', ['updated_at'], {
    name: 'poll_vote_rollups_updated_at_idx',
  });
  await queryInterface.createTable('poll_vote_time_bins_hourly', {
    poll_id: {
      type: DataTypes.STRING(64),
      allowNull: false,
      primaryKey: true,
    },
    hour_bucket_utc: {
      type: DataTypes.DATE,
      allowNull: false,
      primaryKey: true,
    },
    vote_count: {
      type: DataTypes.INTEGER,
      allowNull: false,
      defaultValue: 0,
    },
    updated_at: {
      type: DataTypes.DATE,
      allowNull: false,
      defaultValue: DataTypes.NOW,
    },
  });
  await queryInterface.addIndex('poll_vote_time_bins_hourly', ['hour_bucket_utc'], {
    name: 'poll_vote_time_bins_hourly_bucket_idx',
  });
  await queryInterface.addIndex('poll_vote_time_bins_hourly', ['updated_at'], {
    name: 'poll_vote_time_bins_hourly_updated_at_idx',
  });
  await queryInterface.createTable('poll_vote_geo_bins', {
    poll_id: {
      type: DataTypes.STRING(64),
      allowNull: false,
      primaryKey: true,
    },
    latitude_bucket: {
      type: DataTypes.DECIMAL(4, 1),
      allowNull: false,
      primaryKey: true,
    },
    longitude_bucket: {
      type: DataTypes.DECIMAL(4, 1),
      allowNull: false,
      primaryKey: true,
    },
    vote_count: {
      type: DataTypes.INTEGER,
      allowNull: false,
      defaultValue: 0,
    },
    updated_at: {
      type: DataTypes.DATE,
      allowNull: false,
      defaultValue: DataTypes.NOW,
    },
  });
  await queryInterface.addIndex('poll_vote_geo_bins', ['poll_id', 'vote_count'], {
    name: 'poll_vote_geo_bins_poll_count_idx',
  });
  await queryInterface.addIndex('poll_vote_geo_bins', ['updated_at'], {
    name: 'poll_vote_geo_bins_updated_at_idx',
  });
  await queryInterface.createTable('poll_vote_replay_events', {
    poll_id: {
      type: DataTypes.STRING(64),
      allowNull: false,
      primaryKey: true,
    },
    sequence_no: {
      type: DataTypes.INTEGER,
      allowNull: false,
      primaryKey: true,
    },
    option_label: {
      type: DataTypes.STRING(500),
      allowNull: false,
    },
    offset_ms: {
      type: DataTypes.BIGINT,
      allowNull: false,
      defaultValue: 0,
    },
    updated_at: {
      type: DataTypes.DATE,
      allowNull: false,
      defaultValue: DataTypes.NOW,
    },
  });
  await queryInterface.addIndex('poll_vote_replay_events', ['poll_id', 'sequence_no'], {
    name: 'poll_vote_replay_events_poll_seq_idx',
  });
  await queryInterface.addIndex('poll_vote_replay_events', ['updated_at'], {
    name: 'poll_vote_replay_events_updated_at_idx',
  });
  await queryInterface.sequelize.query(`
    INSERT INTO poll_vote_rollups (
      poll_id,
      total_votes,
      votes_last_1m,
      votes_last_24h,
      quarantined_votes_pending,
      updated_at
    )
    SELECT
      p.id AS poll_id,
      COUNT(v.*) FILTER (WHERE COALESCE(v."isQuarantined", false) = false)::int AS total_votes,
      COUNT(v.*) FILTER (
        WHERE v."createdAt" >= NOW() - INTERVAL '1 minute'
          AND COALESCE(v."isQuarantined", false) = false
      )::int AS votes_last_1m,
      COUNT(v.*) FILTER (
        WHERE v."createdAt" >= NOW() - INTERVAL '24 hours'
          AND COALESCE(v."isQuarantined", false) = false
      )::int AS votes_last_24h,
      COUNT(v.*) FILTER (
        WHERE COALESCE(v."isQuarantined", false) = true
          AND COALESCE(v."quarantineStatus", 'pending') = 'pending'
      )::int AS quarantined_votes_pending,
      NOW() AS updated_at
    FROM polls p
    LEFT JOIN votes v ON v."pollId" = p.id
    GROUP BY p.id
    ON CONFLICT (poll_id) DO UPDATE SET
      total_votes = EXCLUDED.total_votes,
      votes_last_1m = EXCLUDED.votes_last_1m,
      votes_last_24h = EXCLUDED.votes_last_24h,
      quarantined_votes_pending = EXCLUDED.quarantined_votes_pending,
      updated_at = EXCLUDED.updated_at;
  `);
  await queryInterface.sequelize.query(`
    INSERT INTO poll_vote_time_bins_hourly (
      poll_id,
      hour_bucket_utc,
      vote_count,
      updated_at
    )
    SELECT
      v."pollId" AS poll_id,
      date_trunc('hour', v."createdAt" AT TIME ZONE 'UTC') AS hour_bucket_utc,
      COUNT(*)::int AS vote_count,
      NOW() AS updated_at
    FROM votes v
    WHERE COALESCE(v."isQuarantined", false) = false
    GROUP BY v."pollId", date_trunc('hour', v."createdAt" AT TIME ZONE 'UTC')
    ON CONFLICT (poll_id, hour_bucket_utc) DO UPDATE SET
      vote_count = EXCLUDED.vote_count,
      updated_at = EXCLUDED.updated_at;
  `);
  await queryInterface.sequelize.query(`
    INSERT INTO poll_vote_geo_bins (
      poll_id,
      latitude_bucket,
      longitude_bucket,
      vote_count,
      updated_at
    )
    SELECT
      v."pollId" AS poll_id,
      v.vote_latitude::numeric(4,1) AS latitude_bucket,
      v.vote_longitude::numeric(4,1) AS longitude_bucket,
      COUNT(*)::int AS vote_count,
      NOW() AS updated_at
    FROM votes v
    WHERE COALESCE(v."isQuarantined", false) = false
      AND v.vote_latitude IS NOT NULL
      AND v.vote_longitude IS NOT NULL
    GROUP BY
      v."pollId",
      v.vote_latitude::numeric(4,1),
      v.vote_longitude::numeric(4,1)
    ON CONFLICT (poll_id, latitude_bucket, longitude_bucket) DO UPDATE SET
      vote_count = EXCLUDED.vote_count,
      updated_at = EXCLUDED.updated_at;
  `);
  await queryInterface.sequelize.query(`
    INSERT INTO poll_vote_replay_events (
      poll_id,
      sequence_no,
      option_label,
      offset_ms,
      updated_at
    )
    SELECT
      t.poll_id,
      t.sequence_no,
      t.option_label,
      t.offset_ms,
      NOW() AS updated_at
    FROM (
      SELECT
        v."pollId" AS poll_id,
        ROW_NUMBER() OVER (
          PARTITION BY v."pollId"
          ORDER BY v."createdAt" ASC, v.id ASC
        )::int AS sequence_no,
        v.option AS option_label,
        GREATEST(
          0,
          FLOOR(
            EXTRACT(
              EPOCH FROM (
                v."createdAt" - FIRST_VALUE(v."createdAt") OVER (
                  PARTITION BY v."pollId"
                  ORDER BY v."createdAt" ASC, v.id ASC
                )
              )
            ) * 1000
          )
        )::bigint AS offset_ms
      FROM votes v
      WHERE COALESCE(v."isQuarantined", false) = false
    ) t
    ON CONFLICT (poll_id, sequence_no) DO UPDATE SET
      option_label = EXCLUDED.option_label,
      offset_ms = EXCLUDED.offset_ms,
      updated_at = EXCLUDED.updated_at;
  `);

  const qi = queryInterface.sequelize;
  await qi.query(`
    INSERT INTO workspaces (owner_user_id, billing_plan, polar_customer_id, polar_subscription_id)
    SELECT id, billing_plan, polar_customer_id, polar_subscription_id FROM users
  `);
  await qi.query(`
    UPDATE users u
    SET default_workspace_id = w.id
    FROM workspaces w
    WHERE w.owner_user_id = u.id
  `);
  await qi.query(`
    UPDATE polls p
    SET workspace_id = u.default_workspace_id
    FROM users u
    WHERE p."creatorUserId" = u.id AND u.default_workspace_id IS NOT NULL
  `);
}

export async function down(queryInterface: QueryInterface): Promise<void> {
  await queryInterface.dropTable('poll_vote_replay_events');
  await queryInterface.dropTable('poll_vote_geo_bins');
  await queryInterface.dropTable('poll_vote_time_bins_hourly');
  await queryInterface.dropTable('poll_vote_rollups');
  await queryInterface.dropTable('poll_phase_events');
  await queryInterface.dropTable('votes');
  await queryInterface.dropTable('polls');
  await queryInterface.dropTable('workspaces');
  await queryInterface.dropTable('polar_webhook_deliveries');
  await queryInterface.dropTable('users');
  await queryInterface.dropTable('audit_logs');
  await queryInterface.dropTable('status_probe_snapshots');
  await queryInterface.dropTable('app_settings');
}
