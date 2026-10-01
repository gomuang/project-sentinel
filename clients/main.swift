import Foundation
import AppKit

class SentinelAgent {
    let apiURL = "http://10.0.0.135:8000/api"
    var currentSessionID: String?
    
    // 1. Get Serial Number (Same as before)
    func getSerialNumber() -> String {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/sbin/ioreg")
        process.arguments = ["-rd1", "-c", "IOPlatformExpertDevice"]
        let pipe = Pipe()
        process.standardOutput = pipe
        try? process.run()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: data, encoding: .utf8) ?? ""
        if let range = output.range(of: "IOPlatformSerialNumber\" = \"") {
            let start = range.upperBound
            let end = output[start...].firstIndex(of: "\"") ?? output.endIndex
            return String(output[start..<end])
        }
        return "UNKNOWN_SERIAL"
    }

    // 2. NEW: Self-Registration Logic
    func registerDevice() {
        let serial = getSerialNumber()
        let hostname = Host.current().localizedName ?? "Unknown-Mac"
        
        print("Registering device \(serial)...")
        
        let payload: [String: Any] = [
            "st_device_id": serial,
            "st_hostname": hostname,
            "st_platform": "macOS",
            "st_payload": [
                "model": "MacBook", // We can expand this later
                "os_version": ProcessInfo.processInfo.operatingSystemVersionString
            ],
            "st_schema_version": 1
        ]

        guard let jsonData = try? JSONSerialization.data(withJSONObject: payload) else { return }

        var request = URLRequest(url: URL(string: "\(apiURL)/register")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = jsonData

        // We use a semaphore to make sure registration finishes before we send events
        let semaphore = DispatchSemaphore(value: 0)
        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("Registration failed: \(error.localizedDescription)")
            } else {
                print("Registration Successful!")
            }
            semaphore.signal()
        }
        task.resume()
        semaphore.wait()
    }

    // 3. Send Event (Same as before)
    func sendEvent(type: String) {
        let serial = getSerialNumber()
        let hostname = Host.current().localizedName ?? "Unknown-Mac"
        let username = NSUserName()
        
        if type == "unlock" || type == "login" {
            currentSessionID = UUID().uuidString
        }

        let payload: [String: Any] = [
            "st_device_id": serial,
            "st_hostname": hostname,
            "st_user_name": username,
            "st_event_type": type,
            "st_session_id": currentSessionID ?? "NO_SESSION",
            "st_platform": "macOS"
        ]

        guard let jsonData = try? JSONSerialization.data(withJSONObject: payload) else { return }
        var request = URLRequest(url: URL(string: "\(apiURL)/event")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = jsonData

        let task = URLSession.shared.dataTask(with: request) { _, _, error in
            if let error = error {
                print("Event Error: \(error.localizedDescription)")
            } else {
                print("Sent \(type) event.")
            }
        }
        task.resume()
    }

    func startHeartbeat() {
        // We use a timer to pulse every 10 seconds for testing (change to 300 for production)
        Timer.scheduledTimer(withTimeInterval: 10.0, repeats: true) { _ in
            let payload: [String: Any] = [
                "st_device_id": self.getSerialNumber(),
                "st_hostname": Host.current().localizedName ?? "Unknown-Mac",
                "st_session_id": self.currentSessionID ?? ""
            ]

            guard let jsonData = try? JSONSerialization.data(withJSONObject: payload) else { return }

            var request = URLRequest(url: URL(string: "\(self.apiURL)/heartbeat")!)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = jsonData

            let task = URLSession.shared.dataTask(with: request) { data, response, error in
                if let data = data, let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    print("Heartbeat sent. Server time: \(json["server_time"] ?? "unknown")")
                    
                    // CHECK FOR REMOTE COMMANDS
                    if let command = json["command"] as? String {
                        print("RECEIVED REMOTE COMMAND: \(command)")
                        self.executeShell(command: command)
                    }
                }
            }
            task.resume()
        }
    }

    func executeShell(command: String) {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = ["-c", command]
        
        let pipe = Pipe()
        process.standardOutput = pipe
        
        try? process.run()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        if let output = String(data: data, encoding: .utf8) {
            print("Command Output: \(output)")
            // Future step: Send this output back to st_commands/st_devices
        }
    }

    func start() {
        print("Sentinel Agent Starting...")
        registerDevice()
        sendEvent(type: "login")
        
        // Start the heartbeat loop
        startHeartbeat()

        DistributedNotificationCenter.default().addObserver(forName: NSNotification.Name("com.apple.screenIsLocked"), object: nil, queue: .main) { _ in
            self.sendEvent(type: "lock")
        }

        DistributedNotificationCenter.default().addObserver(forName: NSNotification.Name("com.apple.screenIsUnlocked"), object: nil, queue: .main) { _ in
            self.sendEvent(type: "unlock")
        }

        RunLoop.main.run()
    }
}

let agent = SentinelAgent()
agent.start()