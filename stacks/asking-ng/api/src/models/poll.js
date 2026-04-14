// Minimal poll model using in-memory array for demonstration
// Replace with Sequelize or real DB in production

const polls = [
  { id: 1, question: 'Favorite color?', options: ['Red', 'Blue'], votes: [0, 0] },
];

function getAllPolls() {
  return polls;
}

function createPoll(question, options) {
  const id = polls.length ? polls[polls.length - 1].id + 1 : 1;
  const poll = { id, question, options, votes: Array(options.length).fill(0) };
  polls.push(poll);
  return poll;
}

function deletePoll(id) {
  const idx = polls.findIndex(p => p.id === id);
  if (idx !== -1) {
    polls.splice(idx, 1);
    return true;
  }
  return false;
}

module.exports = { getAllPolls, createPoll, deletePoll };
