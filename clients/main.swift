import Foundation
import AppKit

class SentinelAgent {
    // Server URL and enrollment secret come from the environment (set by the
    // MDM-delivered LaunchDaemon plist), never hard-coded.
    let apiURL = ProcessInfo.processInfo.environment["SENTINEL_API_URL"] ?? "http://10.0.0.135:8000/api"
    let enrollmentSecret = ProcessInfo.processInfo.environment["SENTINEL_ENROLLMENT_SECRET"] ?? ""
    var deviceToken: String?
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

    // Attach the device Bearer token, if we have one, to a request.
    func authorize(_ request: inout URLRequest) {
        if let token = deviceToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
    }

    // 2. Self-Registration: sends the enrollment secret, stores the issued token.
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
        request.setValue(enrollmentSecret, forHTTPHeaderField: "X-Enrollment-Secret")
        request.httpBody = jsonData

        // We use a semaphore to make sure registration finishes before we send events
        let semaphore = DispatchSemaphore(value: 0)
        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("Registration failed: \(error.localizedDescription)")
            } else if let data = data,
                      let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let token = json["device_token"] as? String {
                self.deviceToken = token
                print("Registration Successful!")
            } else {
                print("Registration rejected (no token issued).")
            }
            semaphore.signal()
        }
        task.resume()
        semaphore.wait()
    }

    // 3. Send Event
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
        authorize(&request)
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
            self.authorize(&request)
            request.httpBody = jsonData

            let task = URLSession.shared.dataTask(with: request) { data, response, error in
                if let data = data, let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    print("Heartbeat sent. Server time: \(json["server_time"] ?? "unknown")")
                }
            }
            task.resume()
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
