const express = require('express');
const rateLimit = require('express-rate-limit');
const { getPoll, createPoll, updatePoll, voteOnPoll, deletePoll } = require('../controller/poll');

const router = express.Router();

const createPollLimiter = rateLimit({ windowMs: 60 * 1000, max: 30, message: 'Too many polls created, slow down.' });
const voteLimiter = rateLimit({ windowMs: 60 * 1000, max: 60, message: 'Too many votes, slow down.' });

router.get('/:id', getPoll);
router.post('/', createPollLimiter, createPoll);
router.put('/:id', updatePoll);
router.put('/:id/vote', voteLimiter, voteOnPoll);
router.delete('/:id', deletePoll);

module.exports = router;
