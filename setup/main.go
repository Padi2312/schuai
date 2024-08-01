package main

import (
	"bufio"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"time"
)

type WiFiCredentials struct {
	SSID     string
	Password string
	Priority int
}

type TemplateData struct {
	Error              string
	Success            string
	CurrentConnections []string
}

var tpl = template.Must(template.New("form").Parse(`
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WiFi Setup</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f4f4f4;
        }

        h1 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
        }

        form {
            background-color: #ffffff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }

        input[type="text"],
        input[type="password"],
        input[type="number"] {
            width: 100%;
            padding: 8px;
            margin-bottom: 20px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }

        input[type="submit"] {
            background-color: #3498db;
            color: #ffffff;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
        }

        input[type="submit"]:hover {
            background-color: #2980b9;
        }

        .current-connections {
            margin-top: 20px;
            background-color: #f0f0f0;
            padding: 15px;
            border-radius: 4px;
        }

        .current-connections h2 {
            margin-top: 0;
        }

        .connection-button {
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 4px;
        }

        .password-container {
            position: relative;
        }

        .show-password-btn {
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            background: none;
            border: none;
            cursor: pointer;
            font-size: 14px;
            color: #3498db;
        }
    </style>
</head>
<body>
    <h1>WiFi Setup</h1>
    <form method="POST" action="/submit">
        <label for="ssid">SSID:</label>
        <input type="text" id="ssid" name="ssid" required>

        <label for="password">Password:</label>
        <div class="password-container">
            <input type="password" id="password" name="password" required>
            <button type="button" class="show-password-btn" onclick="togglePassword()">Show</button>
        </div>

        <label for="priority">Priority:</label>
        <input type="number" id="priority" name="priority" value="1" required>

        <input type="submit" value="Submit">
    </form>
    
    <div class="current-connections">
        <h2>Current WiFi Connections</h2>
        <ul>
            {{range .CurrentConnections}}
                <li>
                    {{.}}
                    <form method="POST" action="/connect-existing" style="display: inline;">
                        <input type="hidden" name="ssid" value="{{.}}">
                        <button type="submit" class="connection-button">Connect</button>
                    </form>
                </li>
            {{end}}
        </ul>
    </div>

    <script>
        function togglePassword() {
            var passwordInput = document.getElementById("password");
            var showPasswordBtn = document.querySelector(".show-password-btn");
            if (passwordInput.type === "password") {
                passwordInput.type = "text";
                showPasswordBtn.textContent = "Hide";
            } else {
                passwordInput.type = "password";
                showPasswordBtn.textContent = "Show";
            }
        }
    </script>
</body>
</html>
`))

const (
	maxRetries        = 3
	retryDelay        = 5 * time.Second
	connectionTimeout = 30 * time.Second
	debug             = false
)

func main() {
	http.HandleFunc("GET /", formHandler)
	http.HandleFunc("POST /submit", submitHandler)
	http.HandleFunc("POST /connect-existing", connectExistingHandler)

	if !debug {
		if err := activateAccessPoint("wlan0", "setup-pi", "setup-pi"); err != nil {
			log.Fatalf("Failed to activate access point: %v", err)
		}
	}

	log.Println("Server starting on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}

func formHandler(w http.ResponseWriter, r *http.Request) {
	currentConnections := getCurrentConnections()
	tpl.Execute(w, TemplateData{CurrentConnections: currentConnections})
}

func connectExistingHandler(w http.ResponseWriter, r *http.Request) {
	ssid := r.FormValue("ssid")
	log.Printf("Attempting to connect to existing network: %s", ssid)

	creds := WiFiCredentials{
		SSID: ssid,
		// Password and Priority are not needed as they're already in the config
	}

	success := handleConnection(creds)

	if success {
		log.Println("Successfully connected to existing WiFi network with SSID:", creds.SSID)
		if checkInternetConnection() {
			log.Println("Internet connection verified. Exiting...")
			os.Exit(0)
		}
	}

	http.Redirect(w, r, "/", http.StatusSeeOther)
}

func submitHandler(w http.ResponseWriter, r *http.Request) {
	ssid := r.FormValue("ssid")
	password := r.FormValue("password")
	priority, err := strconv.Atoi(r.FormValue("priority"))
	if err != nil {
		log.Printf("Invalid priority value: %v", err)
		http.Redirect(w, r, "/", http.StatusSeeOther)
		return
	}

	creds := WiFiCredentials{
		SSID:     ssid,
		Password: password,
		Priority: priority,
	}

	success := handleConnection(creds)

	if !success {
		log.Println("Failed to connect to WiFi network with SSID:", creds.SSID)
		log.Println("Starting access point again...")
		if err := activateAccessPoint("wlan0", "setup-pi", "setup-pi"); err != nil {
			log.Fatalf("Failed to activate access point: %v", err)
		}
		return
	}

	if !checkInternetConnection() {
		log.Println("Failed to verify internet connection. Starting access point again...")
		if err := activateAccessPoint("wlan0", "setup-pi", "setup-pi"); err != nil {
			log.Fatalf("Failed to activate access point: %v", err)
		}
		return
	}

	os.Exit(0)
}

func handleConnection(creds WiFiCredentials) bool {
	if isSSIDInConfig(creds.SSID) {
		log.Printf("WiFi credentials exist for SSID: %s", creds.SSID)
		if err := restartWpaSupplicant(); err != nil {
			log.Printf("Failed to restart wpa_supplicant: %v", err)
			return false
		}
	} else {
		log.Printf("Adding new WiFi credentials for SSID: %s", creds.SSID)
		if err := connectToWiFi(creds); err != nil {
			log.Printf("Failed to connect to WiFi: %v", err)
			return false
		}
	}

	success := retryConnection(maxRetries)

	if !success {
		log.Println("FAILED: To connect to WiFi network with SSID:", creds.SSID)
		return false
	}

	return true
}

func isSSIDInConfig(ssid string) bool {
	file, err := os.Open("/etc/wpa_supplicant/wpa_supplicant.conf")
	if err != nil {
		log.Printf("Error opening wpa_supplicant.conf: %v", err)
		return false
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		if strings.Contains(scanner.Text(), `ssid="`+ssid+`"`) {
			return true
		}
	}

	if err := scanner.Err(); err != nil {
		log.Printf("Error scanning wpa_supplicant.conf: %v", err)
	}

	return false
}

func connectToWiFi(creds WiFiCredentials) error {
	networkConfig := fmt.Sprintf(`
country=DE
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
ap_scan=1

network={
    ssid="%s"
    psk="%s"
    priority=%d
}`, creds.SSID, creds.Password, creds.Priority)

	writeCmd := exec.Command("sudo", "tee", "/etc/wpa_supplicant/wpa_supplicant.conf")
	writeCmd.Stdin = strings.NewReader(networkConfig)
	if err := runCommand(writeCmd); err != nil {
		return fmt.Errorf("failed to write to wpa_supplicant.conf: %v", err)
	}

	if err := restartWpaSupplicant(); err != nil {
		return fmt.Errorf("failed to restart wpa_supplicant: %v", err)
	}

	log.Printf("Successfully added WiFi credentials with priority: %s %d", creds.SSID, creds.Priority)
	return nil
}

func restartWpaSupplicant() error {
	restartCmd := exec.Command("sudo", "systemctl", "restart", "wpa_supplicant")
	disconnectHotspotCmd := exec.Command("sudo", "nmcli", "connection", "down", "Hotspot")

	if err := runCommand(restartCmd); err != nil {
		return fmt.Errorf("failed to restart wpa_supplicant: %v", err)
	}

	if err := runCommand(disconnectHotspotCmd); err != nil {
		return fmt.Errorf("failed to disconnect hotspot: %v", err)
	}

	log.Println("wpa_supplicant restarted successfully")
	return nil
}

func activateAccessPoint(device, ssid, password string) error {
	activateCmd := exec.Command("sudo", "nmcli", "d", "wifi", "hotspot", "ifname", device, "ssid", ssid, "password", password)
	if err := runCommand(activateCmd); err != nil {
		return fmt.Errorf("failed to activate access point: %v", err)
	}

	log.Println("Access point activated:", ssid)
	return nil
}

func checkWiFiConnection() bool {
	checkCmd := exec.Command("ping", "-c", "4", "-W", "5", "8.8.8.8")
	err := runCommand(checkCmd)
	return err == nil
}

func retryConnection(maxRetries int) bool {
	for i := 0; i < maxRetries; i++ {
		log.Printf("Attempting to connect (attempt %d/%d)...", i+1, maxRetries)
		if err := restartWpaSupplicant(); err != nil {
			log.Printf("Failed to restart wpa_supplicant: %v", err)
			continue
		}

		if checkWiFiConnection() {
			return true
		}

		log.Printf("Connection attempt %d failed. Retrying in %v...", i+1, retryDelay)
		time.Sleep(retryDelay)
	}

	log.Println("Failed to connect after maximum retries")
	return false
}

func checkInternetConnection() bool {
	checkCmd := exec.Command("ping", "-c", "4", "-W", "5", "8.8.8.8")
	err := runCommandWithTimeout(checkCmd, connectionTimeout)
	return err == nil
}

func runCommandWithTimeout(cmd *exec.Cmd, timeout time.Duration) error {
	done := make(chan error, 1)
	go func() {
		done <- cmd.Run()
	}()

	select {
	case err := <-done:
		return err
	case <-time.After(timeout):
		if err := cmd.Process.Kill(); err != nil {
			log.Printf("Failed to kill process: %v", err)
		}
		return fmt.Errorf("command timed out after %v", timeout)
	}
}

func getCurrentConnections() []string {
	content, err := os.ReadFile("/etc/wpa_supplicant/wpa_supplicant.conf")
	if err != nil {
		log.Printf("Error reading wpa_supplicant.conf: %v", err)
		return nil
	}

	re := regexp.MustCompile(`ssid="(.*?)"`)
	matches := re.FindAllStringSubmatch(string(content), -1)

	var connections []string
	for _, match := range matches {
		if len(match) > 1 {
			connections = append(connections, match[1])
		}
	}

	return connections
}

func runCommand(cmd *exec.Cmd) error {
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}