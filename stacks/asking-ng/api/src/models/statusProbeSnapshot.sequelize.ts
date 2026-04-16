import { DataTypes } from 'sequelize';
import sequelize from '../connections';

const StatusProbeSnapshot = sequelize.define(
  'StatusProbeSnapshot',
  {
    id: {
      type: DataTypes.BIGINT,
      autoIncrement: true,
      primaryKey: true,
    },
    livenessOk: {
      type: DataTypes.BOOLEAN,
      allowNull: false,
      field: 'liveness_ok',
    },
    readinessOk: {
      type: DataTypes.BOOLEAN,
      allowNull: false,
      field: 'readiness_ok',
    },
    livenessStatus: {
      type: DataTypes.INTEGER,
      allowNull: false,
      field: 'liveness_status',
    },
    readinessStatus: {
      type: DataTypes.INTEGER,
      allowNull: false,
      field: 'readiness_status',
    },
    createdAt: {
      type: DataTypes.DATE,
      allowNull: false,
      defaultValue: DataTypes.NOW,
      field: 'createdAt',
    },
  },
  {
    tableName: 'status_probe_snapshots',
    timestamps: false,
  },
);

export default StatusProbeSnapshot;
