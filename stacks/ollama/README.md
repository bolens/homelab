# Ollama Stack

Self-hosted Ollama instance with GPU support for running local LLMs.

**Website:** https://ollama.com  
**Docs:** https://ollama.com/docs  
**GitHub:** https://github.com/ollama/ollama  
**Docker image:** https://hub.docker.com/r/ollama/ollama  
**Releases:** https://github.com/ollama/ollama/releases  

## Features

- **NVIDIA GPU**: `docker-compose.yml` includes a `deploy.resources.reservations.devices` block for the NVIDIA runtime (requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)).
- **CPU-only hosts**: If Docker fails to start the container without a GPU driver, comment out the entire `deploy:` block under `ollama`, then `docker compose up -d --force-recreate`.
- **Custom Model Storage**: Store models in a directory you define (`OLLAMA_MODELS_PATH`)
- **Persistent Data**: Models on your path; other data (config, cache) in Docker volume `ollama_data`

## Prerequisites

- Docker and Docker Compose installed
- (Optional) For GPU: NVIDIA Container Toolkit and appropriate drivers

## Setup

1. Run `./prepare-stack.sh` (creates `stack.env` from `stack.env.example` when missing, optional `caddy_snippet.conf`, ensures `monitor` network).

2. (Optional) Edit `stack.env` and set your model storage path; otherwise models use `./models`:
   ```bash
   OLLAMA_MODELS_PATH=/path/to/your/models
   ```
   Other Ollama data (config, cache) is stored in the Docker volume `ollama_data` and is not configurable.

3. Start the stack:
   ```bash
   docker compose --env-file stack.env up -d
   ```

### Portainer

- **Stacks** → **Add stack** → **Repository**, compose path `stacks/ollama/docker-compose.yml`.
- Run `./prepare-stack.sh` on the host first, or create `stack.env` with
  `OLLAMA_MODELS_PATH` and attach the stack to the external `monitor` network
  so Open WebUI and other AI stacks can reach `ollama:11434`.

## Usage

Once running, Ollama is available to containers on `monitor` at
`http://ollama:11434` and through the configured Caddy hostname. The API is
not published directly on the host.

### Managing models via web UI (no `docker exec`)

Use **Open WebUI** (in `docker/stacks/open-webui`) as a web UI to install and manage Ollama models:

1. Start the **ollama** and **open-webui** stacks and set `OLLAMA_BASE_URL` in Open WebUI to `http://ollama:11434` on the shared `monitor` network.
2. In Open WebUI, go to **Settings (gear) → Connections → Ollama** and click the **Manage** (wrench) button.
3. From there you can **pull/install models**, see installed models, and manage the connection.
4. In chat you can also select a model by name; if it’s not installed, Open WebUI can prompt you to download it.

No `docker exec` is required for pulling or maintaining models when using Open WebUI.

### Pull a model (CLI):
```bash
docker exec -it ollama ollama pull llama2
```

### Run a model (CLI):
```bash
docker exec -it ollama ollama run llama2
```

### From other containers:
Other containers connect to Ollama at `http://ollama:11434` on the shared
Docker network. For one-time setup and how other stacks use this backend, see
[SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

## GPU Support

The stack **ships with NVIDIA GPU reservations** in `docker-compose.yml`. Install the driver and Container Toolkit (below), configure the Docker NVIDIA runtime, then deploy.

If you run **CPU-only** and Compose or the engine errors on the `deploy` device reservation, **comment out the `deploy` block** under the `ollama` service and recreate the container.

### 1. Install the NVIDIA driver (if not already)

- **Arch / CachyOS:** `sudo pacman -S nvidia` (or `nvidia-dkms` if you use a custom kernel).
- **Ubuntu/Debian:** Use the driver from your distro (e.g. `ubuntu-drivers install`) or [NVIDIA’s package repo](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/).
- **Fedora/RHEL:** `sudo dnf install akmod-nvidia` (or follow [NVIDIA Container Toolkit guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)).

Reboot if this is the first time installing the driver, then check: `nvidia-smi`.

### 2. Install NVIDIA Container Toolkit

This lets Docker use the GPU inside containers.

- **Arch / CachyOS:**
  ```bash
  sudo pacman -S nvidia-container-toolkit
  ```
- **Ubuntu/Debian:** See [NVIDIA Container Toolkit install guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) (add repo, then `apt install nvidia-container-toolkit`).
- **Fedora/RHEL:** Same guide; use the `dnf` repo and install `nvidia-container-toolkit`.

### 3. Configure Docker to use the NVIDIA runtime

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 4. Deploy Ollama

The `deploy` block is already in `docker-compose.yml`. After the toolkit and Docker runtime are configured:

```bash
docker compose --env-file stack.env up -d --force-recreate
```

Confirm the container sees the GPU: `docker exec ollama nvidia-smi` (or check Ollama’s API/UI).

## Model Storage

Models are stored in the directory specified by `OLLAMA_MODELS_PATH` in your `stack.env` file. This directory is mounted to `/root/.ollama/models` inside the container, which is where Ollama stores all models.

This allows you to:
- Use a large external drive for models (set `OLLAMA_MODELS_PATH` to an absolute path)
- Share models between multiple Ollama instances
- Backup models easily
- Keep models separate from other Ollama data

**Note**: The `ollama_data` Docker volume stores other Ollama data (config, cache, etc.) and is not configurable. Only the models directory is configurable via `OLLAMA_MODELS_PATH`.

## Troubleshooting

### GPU not detected
- Ensure NVIDIA Container Toolkit is installed: `nvidia-container-toolkit`
- Verify GPU is accessible: `nvidia-smi`
- Check Docker can access GPU: `docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi`

### Permission issues with model directory
- Ensure the directory exists and has proper permissions
- The container runs as root, so ensure the directory is writable

### Connection issues from other containers
- Use `http://ollama:11434` when connecting from containers on the same network
- Attach consuming containers to `monitor`; the host port is intentionally unpublished
