import { DataTypes } from 'sequelize';
import sequelize from '../connections';

const User = sequelize.define(
  'User',
  {
    id: {
      type: DataTypes.INTEGER,
      autoIncrement: true,
      primaryKey: true,
    },
    homelab-user: {
      type: DataTypes.STRING,
      allowNull: false,
      unique: true,
    },
    password: {
      type: DataTypes.STRING,
      allowNull: false,
    },
    role: {
      type: DataTypes.STRING,
      allowNull: false,
      defaultValue: 'user',
    },
    active: {
      type: DataTypes.BOOLEAN,
      allowNull: false,
      defaultValue: true,
    },
    llmGatewayToken: {
      type: DataTypes.TEXT,
      allowNull: true,
      field: 'llm_gateway_token',
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
    billingPlan: {
      type: DataTypes.STRING(32),
      allowNull: false,
      defaultValue: 'free',
      field: 'billing_plan',
    },
    defaultWorkspaceId: {
      type: DataTypes.INTEGER,
      allowNull: true,
      field: 'default_workspace_id',
    },
  },
  {
    tableName: 'users',
    timestamps: false,
  },
);

export default User;
