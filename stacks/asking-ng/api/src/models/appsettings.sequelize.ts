import { DataTypes } from 'sequelize';
import sequelize from '../connections';

const AppSetting = sequelize.define(
  'AppSetting',
  {
    key: {
      type: DataTypes.STRING,
      primaryKey: true,
    },
    value: {
      type: DataTypes.TEXT,
      allowNull: false,
    },
    updatedAt: {
      type: DataTypes.DATE,
      allowNull: false,
    },
  },
  {
    tableName: 'app_settings',
    timestamps: false,
  },
);

export default AppSetting;
