import { Sequelize } from 'sequelize';
import { appEnv } from '../lib/env';

function resolveDatabaseUri(): string {
  if (appEnv.databaseUri) {
    return appEnv.databaseUri;
  }
  const user = appEnv.postgresUser;
  const password = appEnv.postgresPassword;
  const database = appEnv.postgresDb;
  const host = appEnv.postgresHost;
  const port = appEnv.postgresPort;
  if (!user || password === undefined || !database) {
    throw new Error(
      'Database configuration missing: set DATABASE_URI or POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB (e.g. in stack.env).',
    );
  }
  const encUser = encodeURIComponent(user);
  const encPass = encodeURIComponent(password);
  const encDb = encodeURIComponent(database);
  return `postgres://${encUser}:${encPass}@${host}:${port}/${encDb}`;
}

const sequelize = new Sequelize(resolveDatabaseUri());

sequelize
  .authenticate()
  .then(() => {
    console.info('api has successfully connected to database.');
  })
  .catch((err: unknown) => {
    console.error('api has failed to connect to database.', err);
  });

export default sequelize;
