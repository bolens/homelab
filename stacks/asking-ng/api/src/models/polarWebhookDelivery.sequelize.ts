import { DataTypes } from 'sequelize';
import sequelize from '../connections';

const PolarWebhookDelivery = sequelize.define(
  'PolarWebhookDelivery',
  {
    webhookId: {
      type: DataTypes.STRING(128),
      primaryKey: true,
      allowNull: false,
      field: 'webhook_id',
    },
    eventType: {
      type: DataTypes.STRING(128),
      allowNull: false,
      field: 'event_type',
    },
    createdAt: {
      type: DataTypes.DATE,
      allowNull: false,
      field: 'created_at',
      defaultValue: DataTypes.NOW,
    },
  },
  {
    tableName: 'polar_webhook_deliveries',
    timestamps: false,
  },
);

export default PolarWebhookDelivery;
