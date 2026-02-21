# Ollama Stack

Self-hosted Ollama instance with GPU support for running local LLMs.

## Features

- **CPU by default**: Runs without a GPU; no NVIDIA driver required to deploy.
- **Optional GPU**: Uncomment the `deploy` block in `docker-compose.yml` when NVIDIA Container Toolkit is installed.
- **Custom Model Storage**: Store models in a directory you define (`OLLAMA_MODELS_PATH`)
- **Persistent Data**: Models on your path; other data (config, cache) in Docker volume `ollama_data`

## Prerequisites

- Docker and Docker Compose installed
- (Optional) For GPU: NVIDIA Container Toolkit and appropriate drivers

## Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. (Optional) Edit `.env` and set your model storage path; otherwise models use `./models`:
   ```bash
   OLLAMA_MODELS_PATH=/path/to/your/models
   ```
   Other Ollama data (config, cache) is stored in the Docker volume `ollama_data` and is not configurable.

3. Start the stack:
   ```bash
   docker compose up -d
   ```

## Usage

Once running, Ollama will be available at `http://localhost:11434` (or your configured port).

### Managing models via web UI (no `docker exec`)

Use **Open WebUI** (in `docker/stacks/open-webui`) as a web UI to install and manage Ollama models:

1. Start the **ollama** and **open-webui** stacks and set `OLLAMA_BASE_URL` in Open WebUI to point at Ollama (e.g. `http://host.docker.internal:11434` or `http://ollama:11434` if on the same network).
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
Other containers can connect to Ollama at `http://ollama:11434` (on the same Docker network) or `http://host.docker.internal:11434` (from host gateway).

## GPU Support

The stack runs in **CPU-only mode by default**, so it deploys even when no NVIDIA driver is available.

To use an **NVIDIA GPU**:

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

### 4. Enable GPU in the Ollama stack

In `stacks/ollama/docker-compose.yml`, uncomment the `deploy` block under the `ollama` service (the `resources.reservations.devices` section with `driver: nvidia`). Then:

```bash
docker compose up -d --force-recreate
```

To confirm the container sees the GPU: `docker exec ollama nvidia-smi` (or check Ollama’s API/UI).

## Model Storage

Models are stored in the directory specified by `OLLAMA_MODELS_PATH` in your `.env` file. This directory is mounted to `/root/.ollama/models` inside the container, which is where Ollama stores all models.

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
- Use `http://host.docker.internal:11434` when connecting from containers using host gateway
