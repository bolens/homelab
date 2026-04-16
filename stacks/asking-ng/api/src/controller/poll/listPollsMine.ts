import type { ListPollsMineQuery } from '@asking-ng/contracts/poll';
import type { AppRequestHandler } from '../../types/http';
import { presentPollsMineResponse } from './listPollsMine.presenter';
import { buildPollsMineView } from './listPollsMine.service';

const listPollsMine: AppRequestHandler = async (req, res) => {
  const view = await buildPollsMineView(req, req.validatedQuery as ListPollsMineQuery);
  res.json(presentPollsMineResponse(view));
};

export default listPollsMine;
