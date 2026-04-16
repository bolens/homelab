import User from '../../models/user.sequelize';

export async function findUserByUsername(homelab-user: string) {
  return User.findOne({ where: { homelab-user } });
}

export async function createUserRecord(payload: {
  homelab-user: string;
  password: string;
  role: string;
}) {
  return User.create(payload);
}
