import type { QueryInterface } from 'sequelize';
import { DataTypes } from 'sequelize';

/**
 * Adds `workspaces.polar_subscription_status` (last known Polar `subscription.status`) for hosted UX
 * (e.g. past-due banner) without an extra Polar API call per page view.
 */
export async function up(queryInterface: QueryInterface): Promise<void> {
  const dialect = queryInterface.sequelize.getDialect();
  if (dialect !== 'postgres') {
    await queryInterface.addColumn('workspaces', 'polar_subscription_status', {
      type: DataTypes.STRING(32),
      allowNull: true,
    });
    return;
  }
  const [rows] = await queryInterface.sequelize.query(
    `SELECT 1 FROM information_schema.columns
     WHERE table_schema = current_schema() AND table_name = 'workspaces' AND column_name = 'polar_subscription_status'
     LIMIT 1`,
  );
  if (Array.isArray(rows) && rows.length > 0) return;
  await queryInterface.addColumn('workspaces', 'polar_subscription_status', {
    type: DataTypes.STRING(32),
    allowNull: true,
  });
}

export async function down(queryInterface: QueryInterface): Promise<void> {
  await queryInterface.removeColumn('workspaces', 'polar_subscription_status').catch(() => undefined);
}
