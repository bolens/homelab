import { DataTypes } from 'sequelize';
import db from '../connections';
import Poll from './Poll';

const Vote = db.define('vote', {
  id: { primaryKey: true, type: DataTypes.STRING },
  option: DataTypes.STRING,
  weight: { type: DataTypes.INTEGER, allowNull: false, defaultValue: 1 },
  sourceIpHash: { type: DataTypes.STRING(64), allowNull: true },
  userId: { type: DataTypes.INTEGER, allowNull: true },
  commandIdempotencyKey: { type: DataTypes.STRING(128), allowNull: true },
  chatChannelId: { type: DataTypes.STRING(128), allowNull: true },
  isQuarantined: { type: DataTypes.BOOLEAN, allowNull: false, defaultValue: false },
  quarantineReason: { type: DataTypes.STRING(64), allowNull: true },
  quarantineStatus: { type: DataTypes.STRING(16), allowNull: true },
  quarantineDecidedAt: { type: DataTypes.DATE, allowNull: true },
  quarantineDecidedBy: { type: DataTypes.INTEGER, allowNull: true },
  quarantineNote: { type: DataTypes.STRING(500), allowNull: true },
  trustRiskScore: { type: DataTypes.SMALLINT, allowNull: true },
  vote_latitude: { type: DataTypes.DECIMAL(4, 1), allowNull: true },
  vote_longitude: { type: DataTypes.DECIMAL(5, 1), allowNull: true },
});

Vote.belongsTo(Poll);

export default Vote;
