Links

* https://discord.com/developers/applications
* https://discord.com/developers/teams
* https://lubelogger.homelab.arpa/api

## Working Dir

After a `git clone` and running `install.sh` the working dir will be `/opt/lubelogger-bot`

im running this in the lubelogger LXC so it is all in one place

```bash
sudo bash install.sh
sudo systemctl start lubelogger-bot
journalctl -u lubelogger-bot -f
sudo systemctl restart lubelogger-bot
```