import { DataTypes } from 'sequelize';
import sequelize from '../connections';

/** Default billing workspace per owner user (v1: one row per `owner_user_id`). */
const Workspace = sequelize.define(
  'Workspace',
  {
    id: {
      type: DataTypes.INTEGER,
      autoIncrement: true,
      primaryKey: true,
    },
    ownerUserId: {
      type: DataTypes.INTEGER,
      allowNull: false,
      field: 'owner_user_id',
    },
    billingPlan: {
      type: DataTypes.STRING(32),
      allowNull: false,
      defaultValue: 'free',
      field: 'billing_plan',
    },
    polarCustomerId: {
      type: DataTypes.STRING(255),
      allowNull: true,
      field: 'polar_customer_id',
    },
    polarSubscriptionId: {
      type: DataTypes.STRING(255),
      allowNull: true,
      field: 'polar_subscription_id',
    },
    polarSubscriptionStatus: {
      type: DataTypes.STRING(32),
      allowNull: true,
      field: 'polar_subscription_status',
    },
  },
  {
    tableName: 'workspaces',
    timestamps: false,
  },
);

export default Workspace;
