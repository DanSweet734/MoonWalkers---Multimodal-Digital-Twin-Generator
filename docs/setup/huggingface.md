# Connecting a Hugging Face account

Some model weights we use are **gated**: you must accept the model's conditions in a browser before you can
download them. Stable Fast 3D is gated
("you have to accept the conditions", https://huggingface.co/stabilityai/stable-fast-3d).

## 1. Accept the model's conditions (browser only)
1. Sign in at https://huggingface.co.
2. Open the model page (start with https://huggingface.co/stabilityai/stable-fast-3d) and click **Agree**.
   Per Hugging Face's docs, "Requesting access can only be done from your browser," and access is granted
   either immediately (automatic approval) or after the authors review it (manual approval)
   (https://huggingface.co/docs/hub/models-gated).
3. When you open the Hunyuan3D model pages linked from https://github.com/Tencent-Hunyuan/Hunyuan3D-2,
   check whether they ask you to accept conditions too, and accept if so.

## 2. Create a read-only token
Create a User Access Token at https://huggingface.co/settings/tokens. Hugging Face recommends a `read`
token unless you need to upload: "it's best to generate a `read` token to reduce risk in case your token
is inadvertently leaked" (https://huggingface.co/docs/huggingface_hub/en/quick-start).

## 3. Log in on your machine
1. Install the Hugging Face CLI (this is an install, so Claude Code will ask you first):
   `pip install --upgrade huggingface_hub` (or `uv tool install huggingface_hub`).
2. Run `hf auth login`. If you are not logged in, it opens a browser flow: "open the printed URL, enter the
   short code, approve the request, and an access token is retrieved and saved in your `HF_HOME` directory
   (defaults to `~/.cache/huggingface/token`)" (same quick-start page).
3. Alternative: put the token in `.env` as `HF_TOKEN=...`. Per the same page, "Authentication via an
   environment variable or a secret has priority over the token stored on your machine."

## Rules
- Never paste the token into chat, code, commits, or docs. `.env` is gitignored and Claude Code is denied
  from reading it.
- Large weights download to the Hugging Face cache, not the repo.
