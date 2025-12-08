Create the Web Server Service File

Run this command to create the first service file:

Bash
sudo nano /etc/systemd/system/web_server.service
Paste this content inside:

Ini, TOML
[Unit]
Description=Image Web Server for ThingsBoard
After=network.target

[Service]
User=cameramodule
WorkingDirectory=/home/cameramodule/Desktop/MASTER_V5/
ExecStart=/usr/bin/python3 /home/cameramodule/Desktop/MASTER_V5/web_server.py
Restart=always

[Install]
WantedBy=multi-user.target
Save and exit (press Ctrl+X, then Y, then Enter).

2. Create the Main Service File

Now, create the second service file for your main.py script:

Bash
sudo nano /etc/systemd/system/main_service.service
Paste this content inside:

Ini, TOML
[Unit]
Description=ThingsBoard Master Service (main.py)
Wants=web_server.service
After=network.target web_server.service

[Service]
User=cameramodule
WorkingDirectory=/home/cameramodule/Desktop/MASTER_V5/
ExecStart=/usr/bin/python3 /home/cameramodule/Desktop/MASTER_V5/main.py
Restart=always

[Install]
WantedBy=multi-user.target
Save and exit (Ctrl+X, Y, Enter).

3. Enable and Start the Services

Finally, tell systemd to load and run your new services.

Reload systemd to read the new files:
sudo systemctl daemon-reload

Enable the services (makes them start automatically on boot):
sudo systemctl enable web_server.service
sudo systemctl enable main_service.service

Start the services now:
sudo systemctl start web_server.service
sudo systemctl start main_service.service

Your scripts are now running as background services. They will start automatically when the Pi boots up and restart if they crash.

You can check their status any time with:
sudo systemctl status main_service.service 

or see their live log output with:
journalctl -u main_service.service -f

________________________________________________________________________________________________________________________________________
________________________________________________________________________________________________________________________________________





Here are the commands you can use to manage your new services:

Check Status:
sudo systemctl status main_service.service
sudo systemctl status web_server.service

Watch Live Logs: (This is your new way to see print statements or logger output)
journalctl -u main_service.service -f
(Press Ctrl+C to exit the live view)

Stop a Service:
sudo systemctl stop main_service.service

Start a Service Manually:
sudo systemctl start main_service.service

Restart a Service: (Very useful if you make changes to your Python code)
sudo systemctl restart main_service.service

