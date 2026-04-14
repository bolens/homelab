// Minimal user model using in-memory array for demonstration
// Replace with Sequelize or real DB in production

const users = [
  { id: 1, homelab-user: 'admin', role: 'admin' },
  { id: 2, homelab-user: 'user1', role: 'user' },
];

function getAllUsers() {
  return users;
}

function createUser(homelab-user, role = 'user') {
  const id = users.length ? users[users.length - 1].id + 1 : 1;
  const user = { id, homelab-user, role };
  users.push(user);
  return user;
}

function deleteUser(id) {
  const idx = users.findIndex(u => u.id === id);
  if (idx !== -1) {
    users.splice(idx, 1);
    return true;
  }
  return false;
}

module.exports = { getAllUsers, createUser, deleteUser };
