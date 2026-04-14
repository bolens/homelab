#!/bin/bash
# Start both backend and frontend for asking-ng

# Start backend (API)
(cd ../api && pnpm start &)

# Start frontend (client)
pnpm start
