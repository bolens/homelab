import User from '../../models/user.sequelize';

const userAttributes = ['id', 'homelab-user', 'role'];

export async function listUsers() {
  return User.findAll({ attributes: userAttributes });
}

export async function findUserById(id: number) {
  return User.findByPk(id);
}

export async function findUserSummaryById(id: number) {
  return User.findByPk(id, { attributes: userAttributes });
}

export async function createUserRecord(payload: {
  homelab-user: string;
  password: string;
  role: string;
}) {
  return User.create(payload);
}

export async function deleteUserById(id: number) {
  return User.destroy({ where: { id } });
}
