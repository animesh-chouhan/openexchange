# OpenExchange — Service status & quick checks

This file lists quick commands to check and troubleshoot the OpenExchange service on the host.

## Service status

- Show current status and recent state:

```bash
sudo systemctl status openexchange.service
```

- Active? (returns `active`/`inactive`/`failed`):

```bash
sudo systemctl is-active openexchange.service
```

## Logs

- Follow live journal logs for the service:

```bash
sudo journalctl -u openexchange.service -f
```

- Show logs for the last 10 minutes:

```bash
sudo journalctl -u openexchange.service --since "10 minutes ago"
```

## Process and port checks

- Check for the uvicorn/python process:

```bash
ps aux | grep -E 'uvicorn|server:app' | grep -v grep
```

- Check listening ports (look for :8000):

```bash
sudo ss -ltnp | grep :8000
```

## HTTP checks

- Test the app directly (uvicorn):

```bash
curl -v http://127.0.0.1:8000/
```

- Test via nginx (if nginx is fronting the app):

```bash
curl -v http://localhost/
```

## Nginx

- Check nginx status and recent logs:

```bash
sudo systemctl status nginx
sudo journalctl -u nginx -f
```

- Test nginx configuration syntax:

```bash
sudo nginx -t
```

- If the project includes `server/nginx.conf`, the setup process copies it to `/etc/nginx/sites-available/openexchange.conf` and enables it.

## Firewall (UFW)

- See current rules:

```bash
sudo ufw status verbose
```

- Allow a port (example):

```bash
sudo ufw allow 8000/tcp
```

## Inspect installed unit file

If you need to inspect the unit that was installed by the setup script, open:

[server/openexchange.service](server/openexchange.service#L1)

Common items to check in the unit:

- `ExecStart` points to the Python/uvicorn binary in the activated venv.
- `User`/`Group` and `WorkingDirectory` are correct for your deployment.

## Quick recovery steps

1. Check service logs: `sudo journalctl -u openexchange.service -n 200 --no-pager`
2. Inspect unit file: `sudo systemctl cat openexchange.service`
3. Reload systemd units: `sudo systemctl daemon-reload`
4. Restart the service: `sudo systemctl restart openexchange.service`
5. If nginx is used, test config and reload: `sudo nginx -t && sudo systemctl reload nginx`

## When to share output here

If you see failures, copy the output of these commands when asking for help:

```bash
sudo systemctl status openexchange.service --no-pager
sudo journalctl -u openexchange.service -n 300 --no-pager
sudo nginx -t || true
sudo ufw status verbose || true
sudo ss -ltnp | grep :8000 || true
```

Paste the outputs and I will help interpret them.
