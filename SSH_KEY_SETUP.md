# SSH Key Setup for Zeek VM Access

## Current Status
- **FastAPI VM (34.170.121.14)**: This is where you're currently working
- **Zeek VM (35.222.249.202)**: Remote Zeek sensor - SSH key needed
- **PostgreSQL VM (34.132.194.35)**: Already reachable via network

## The ED25519 Public Key (for Zeek VM)

Add this key to the Zeek VM's `authorized_keys`:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM0/uleNqaE05oote+mJx3XfwP4EQ7mtKOUey0W7kDlF zauguste52@cis493-fa25-vm1.us-central1-c.c.senior-design-365100.internal
```

## How to Add This Key to Zeek VM

### Option 1: If you have SSH access already (or can SSH to Zeek VM):
```bash
ssh zauguste52@35.222.249.202
mkdir -p ~/.ssh
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM0/uleNqaE05oote+mJx3XfwP4EQ7mtKOUey0W7kDlF zauguste52@cis493-fa25-vm1.us-central1-c.c.senior-design-365100.internal' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

### Option 2: Using Google Cloud Console (if both VMs are in same GCP project):
1. Go to Google Cloud Console
2. SSH into the Zeek VM (35.222.249.202) using the browser console
3. Run the commands from Option 1 above

### Option 3: Using `gcloud` CLI:
```bash
gcloud compute ssh zauguste52@cis493-fa25-vm1 --zone=us-central1-c << 'EOF'
mkdir -p ~/.ssh
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM0/uleNqaE05oote+mJx3XfwP4EQ7mtKOUey0W7kDlF zauguste52@cis493-fa25-vm1.us-central1-c.c.senior-design-365100.internal' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
EOF
```

## After Key is Added

Once the ED25519 key is added to the Zeek VM's `authorized_keys`, test the connection:

```bash
# From FastAPI VM (34.170.121.14):
ssh -i /home/zauguste52/.ssh/id_ed25519 zauguste52@35.222.249.202 "ls /opt/zeek/logs/current/"
```

If successful, you should see Zeek log files like:
- conn.log
- dns.log
- http.log
- ssl.log
- files.log
- etc.

## Keys Available on FastAPI VM

### ED25519 Key (Modern, Recommended)
- **Private Key**: `/home/zauguste52/.ssh/id_ed25519`
- **Public Key**: `/home/zauguste52/.ssh/id_ed25519.pub`
- **Type**: ssh-ed25519
- **Status**: ✅ Ready to use

### RSA Key (Legacy)
- **Private Key**: `/home/zauguste52/.ssh/id_rsa`
- **Status**: ❌ Currently corrupted (invalid format)

## Configuration

Your `.env` file has been updated with:

```bash
export ZEEK_REMOTE_HOST="35.222.249.202"
export ZEEK_REMOTE_USER="zauguste52"
export ZEEK_SSH_KEY="/home/zauguste52/.ssh/id_ed25519"
export ZEEK_SSH_PASSPHRASE=""
export ZEEK_REMOTE_LOG_DIR="/opt/zeek/logs/current"
```

These settings will be used by the FastAPI Zeek Remote endpoints to:
1. Connect to the Zeek VM via SSH
2. List available log files
3. Download and ingest logs to PostgreSQL

## Next Steps

1. **Add ED25519 public key to Zeek VM's authorized_keys**
2. Test SSH connection: `ssh -i ~/.ssh/id_ed25519 zauguste52@35.222.249.202`
3. Test Zeek log access: `ssh ... "ls /opt/zeek/logs/current/"`
4. Start FastAPI: `python -m backend.app.main`
5. Test ingestion endpoint: `curl http://localhost:8000/zeek/remote/test-connection`
6. Monitor logs: `curl http://localhost:8000/zeek/remote/list-logs`

## Troubleshooting

### SSH connection refused
- ED25519 key not added to Zeek VM's authorized_keys
- Username is wrong (should be `zauguste52`)
- IP address is wrong (should be `35.222.249.202`)

### Permission denied (publickey)
- The public key in `authorized_keys` doesn't match your private key
- The `authorized_keys` file has wrong permissions (should be 600)
- The `.ssh` directory has wrong permissions (should be 700)

### SSH timeout
- Network connectivity issue
- Zeek VM firewall blocking port 22
- Check: `nc -zv 35.222.249.202 22`

## Access from Other Machines

If you want to access the FastAPI VM from another machine, add that machine's public key to:

```bash
/home/zauguste52/.ssh/authorized_keys
```

The FastAPI VM already has these authorized keys:
- RSA keys from gmail.com and other sources
- ED25519 keys from various workstations

Current accessible public key for this FastAPI VM:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM0/uleNqaE05oote+mJx3XfwP4EQ7mtKOUey0W7kDlF zauguste52@cis493-fa25-vm1.us-central1-c.c.senior-design-365100.internal
```
