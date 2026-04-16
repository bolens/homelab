import type { QueryInterface } from 'sequelize';
import { SequelizeStorage, Umzug } from 'umzug';

// Side-effect: register every Sequelize model before baseline `sync()` runs.
import '../models/auditlog.sequelize';
import '../models/appsettings.sequelize';
import '../models/user.sequelize';
import '../models/workspace.sequelize';
import '../models/polarWebhookDelivery.sequelize';
import '../models/statusProbeSnapshot.sequelize';
import '../model/Poll';
import '../model/Vote';

import * as baselinePrelaunch from '../migrations/00-baseline-prelaunch';
import sequelize from '../models';
import { logger } from './logger';

export async function runMigrations(): Promise<void> {
  const umzug = new Umzug({
    migrations: [
      {
        name: '00-baseline-prelaunch',
        up: async ({ context }) => {
          await baselinePrelaunch.up(context as QueryInterface);
        },
        down: async ({ context }) => {
          await baselinePrelaunch.down(context as QueryInterface);
        },
      },
    ],
    context: sequelize.getQueryInterface(),
    storage: new SequelizeStorage({ sequelize }),
    logger: {
      info: (msg) => logger.info({ event: 'db.migrate.umzug_info', detail: String(msg) }),
      warn: (msg) => logger.warn({ event: 'db.migrate.umzug_warn', detail: String(msg) }),
      error: (msg) => logger.error({ event: 'db.migrate.umzug_error', detail: String(msg) }),
      debug: (msg) => logger.debug({ event: 'db.migrate.umzug_debug', detail: String(msg) }),
    },
  });
  await umzug.up();
  logger.info({ event: 'db.migrate.applied' }, 'database migrations applied');
}
