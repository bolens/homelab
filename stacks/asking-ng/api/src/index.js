const express = require('express');
const morgan = require('morgan');
const cors = require('cors');
const helmet = require('helmet');
const requestIp = require('request-ip');

const baseRoute = require('./routes/base');
const pollRoute = require('./routes/poll');
const adminRoute = require('./admin');
const rateLimit = require('express-rate-limit');

// Sequelize DB sync (single connection; register all models before sync)
const sequelize = require('./models');
require('./models/user.sequelize');
require('./models/auditlog.sequelize');
require('./model/Poll');
require('./model/Vote');

// express app
const app = express();

// configure port for api
app.set('port', process.env.PORT || 3001);

// middleware
app.use(morgan('dev'));
app.use(cors());
app.use(helmet());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(requestIp.mw());

// Rate limiting
const authLimiter = rateLimit({ windowMs: 15 * 60 * 1000, max: 10, message: 'Too many attempts, try again later.' });
const adminLimiter = rateLimit({ windowMs: 15 * 60 * 1000, max: 30, message: 'Too many admin requests.' });

// Apply to sensitive endpoints
app.use(['/auth/login', '/auth/register'], authLimiter);
app.use('/admin', adminLimiter);

app.set('trust proxy', 1);

// map routes to routers
app.use('/', baseRoute);
app.use('/poll', pollRoute);
app.use('/admin', adminRoute);

// Sync DB and start server
sequelize.sync({ alter: true }).then(() => {
  app.listen(app.get('port'), () => {
    console.info(`api server is listening on port ${app.get('port')}`);
  });
}).catch((err) => {
  console.error('Failed to sync database:', err);
  process.exit(1);
});
