package main

import (
	"bufio"
	"html/template"
	"log"
	"net/http"
	"os"
	"os/exec"
	"strconv"
	"strings"
)

type WiFiCredentials struct {
	SSID     string
	Password string
	Priority int
}

var tpl = template.Must(template.New("form").Parse(`
<!DOCTYPE html>
<html>
<head>
    <title>WiFi Setup</title>
</head>
<body>
    <h1>WiFi Setup</h1>
    <form method="POST" action="/submit">
        <label for="ssid">SSID:</label>
        <input type="text" id="ssid" name="ssid" required><br><br>
        <label for="password">Password:</label>
        <input type="password" id="password" name="password" required><br><br>
        <label for="priority">Priority:</label>
        <input type="number" id="priority" name="priority" value="1" required><br><br>
        <input type="submit" value="Submit">
    </form>
</body>
</html>
`))

func main() {
	http.HandleFunc("/", formHandler)
	http.HandleFunc("/submit", submitHandler)
	activateAccessPoint("wlan0", "RaspberryPiAP", "raspberry")
	log.Println("Server starting on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}

func formHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Invalid request method", http.StatusMethodNotAllowed)
		return
	}
	tpl.Execute(w, nil)
}

func submitHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Invalid request method", http.StatusMethodNotAllowed)
		return
	}
	ssid := r.FormValue("ssid")
	password := r.FormValue("password")
	priority, err := strconv.Atoi(r.FormValue("priority"))
	if err != nil {
		http.Error(w, "Invalid priority value", http.StatusBadRequest)
		return
	}

	creds := WiFiCredentials{
		SSID:     ssid,
		Password: password,
		Priority: priority,
	}

	if !isSSIDInConfig(creds.SSID) {
		// Execute commands to connect to WiFi
		connectToWiFi(creds)
		w.Write([]byte("WiFi credentials submitted. Attempting to connect..."))
		if !checkWiFiConnection() {
			removeSSIDFromConfig(creds.SSID)
			w.Write([]byte("WiFi connection failed. Credentials removed."))
		}
	} else {
		w.Write([]byte("WiFi credentials already exist. Attempting to reconnect..."))
		restartWpaSupplicant()
	}
}

func isSSIDInConfig(ssid string) bool {
	file, err := os.Open("/etc/wpa_supplicant/wpa_supplicant.conf")
	if err != nil {
		log.Fatal(err)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		if strings.Contains(scanner.Text(), `ssid="`+ssid+`"`) {
			return true
		}
	}

	if err := scanner.Err(); err != nil {
		log.Fatal(err)
	}

	return false
}

func connectToWiFi(creds WiFiCredentials) {
	cmd := exec.Command("sh", "-c", `
    sudo bash -c 'echo "
network={
    ssid=\"`+creds.SSID+`\"
    psk=\"`+creds.Password+`\"
    priority=`+strconv.Itoa(creds.Priority)+`
}" >> /etc/wpa_supplicant/wpa_supplicant.conf'
    sudo systemctl restart wpa_supplicant
    sudo nmcli connection down Hotspot
    `)

	if err := cmd.Run(); err != nil {
		log.Println("Error connecting to WiFi:", err)
	} else {
		log.Println("Successfully added WiFi credentials with priority:", creds.SSID, creds.Priority)
	}
}

func restartWpaSupplicant() {
	cmd := exec.Command("sh", "-c", `
    sudo systemctl restart wpa_supplicant
    sudo nmcli connection down Hotspot
    `)

	if err := cmd.Run(); err != nil {
		log.Println("Error restarting wpa_supplicant:", err)
	} else {
		log.Println("wpa_supplicant restarted successfully")
	}
}

func activateAccessPoint(device string, ssid string, password string) {
	cmd := exec.Command("sudo", "nmcli", "d", "wifi", "hotspot", "ifname", device, "ssid", ssid, "password", password)
	if err := cmd.Run(); err != nil {
		log.Println("Error activating access point:", err)
	} else {
		log.Println("Access point activated:", ssid)
	}
}

func checkWiFiConnection() bool {
	cmd := exec.Command("sh", "-c", `
    ping -c 4 8.8.8.8 > /dev/null 2>&1
    `)
	err := cmd.Run()
	return err == nil
}

func removeSSIDFromConfig(ssid string) {
	input, err := os.ReadFile("/etc/wpa_supplicant/wpa_supplicant.conf")
	if err != nil {
		log.Fatal(err)
	}

	lines := strings.Split(string(input), "\n")
	var output []string
	inNetworkBlock := false

	for _, line := range lines {
		if strings.Contains(line, `ssid="`+ssid+`"`) {
			inNetworkBlock = true
		}
		if inNetworkBlock {
			if strings.Contains(line, "}") {
				inNetworkBlock = false
				continue
			}
			continue
		}
		output = append(output, line)
	}

	err = os.WriteFile("/etc/wpa_supplicant/wpa_supplicant.conf", []byte(strings.Join(output, "\n")), 0644)
	if err != nil {
		log.Fatal(err)
	}
	log.Println("Removed SSID from wpa_supplicant.conf:", ssid)
}
