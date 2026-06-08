using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

public class RobotUDPReceiver : MonoBehaviour
{
    [Header("Network Settings")]
    public int port = 5005;

    [Header("Robot Links")]
    public ArticulationBody[] robotJoints = new ArticulationBody[6];

    [Header("Gripper Links (Optional)")]
    public ArticulationBody[] gripperJoints = new ArticulationBody[0];
    public float gripperOpenAngle = 0f;
    public float gripperCloseAngle = 40f;

    private UdpClient udpClient;
    private Thread receiveThread;
    private float[] incomingPythonAngles = new float[6];
    private float incomingPythonGripper = 0f; // 0% = open, 100% = closed
    private float[] activeTargets = new float[6]; // Smoothly tracking targets
    private float activeGripperNormalized = 0f; // 0% = open, 100% = closed (0.0 to 1.0)
    private bool isRunning = true;
    private bool isInitialized = false;
    private int packetCount = 0;
    private readonly object lockObject = new object();

    void Start()
    {
        Debug.Log("[UDP Receiver] System initializing...");
        LoadConfigurations();

        // Ensure joints have sufficient force capacity to track targets precisely
        foreach (ArticulationBody joint in robotJoints)
        {
            if (joint != null)
            {
                var drive = joint.xDrive;
                drive.forceLimit = 1000f; // High force limit overrides low editor limits (like 9)
                joint.xDrive = drive;
            }
        }

        // Initialize gripper force limits
        foreach (ArticulationBody finger in gripperJoints)
        {
            if (finger != null)
            {
                var drive = finger.xDrive;
                drive.forceLimit = 1000f;
                finger.xDrive = drive;

                bool isRight = IsRightSide(finger.gameObject);
                Debug.Log($"[UDP Receiver] Gripper Joint: '{finger.gameObject.name}' -> Classified as {(isRight ? "RIGHT" : "LEFT")} side.");
            }
        }

        receiveThread = new Thread(ReceiveData)
        {
            IsBackground = true
        };
        receiveThread.Start();
    }

    private void ReceiveData()
    {
        try
        {
            udpClient = new UdpClient(port);
        }
        catch (Exception e)
        {
            Debug.LogError($"[UDP Receiver] Port error: {e.Message}");
            return;
        }

        IPEndPoint anyIP = new IPEndPoint(IPAddress.Any, 0);

        while (isRunning)
        {
            try
            {
                byte[] data = udpClient.Receive(ref anyIP);
                string csvString = Encoding.UTF8.GetString(data);
                string[] tokens = csvString.Split(',');
                
                if (tokens != null && (tokens.Length == 6 || tokens.Length == 7))
                {
                    float[] receivedAngles = new float[6];
                    float receivedGripper = 0f;
                    bool parseSuccess = true;
                    
                    for (int i = 0; i < 6; i++)
                    {
                        if (!float.TryParse(tokens[i], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out receivedAngles[i]))
                        {
                            parseSuccess = false;
                            break;
                        }
                    }

                    if (tokens.Length == 7)
                    {
                        if (!float.TryParse(tokens[6], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out receivedGripper))
                        {
                            parseSuccess = false;
                        }
                    }

                    if (parseSuccess)
                    {
                        lock (lockObject)
                        {
                            Array.Copy(receivedAngles, incomingPythonAngles, 6);
                            if (tokens.Length == 7)
                            {
                                incomingPythonGripper = receivedGripper;
                            }
                        }

                        packetCount++;
                        if (packetCount % 10 == 0)
                        {
                            if (tokens.Length == 7)
                            {
                                Debug.Log($"[UDP Receiver] Telemetry incoming... Packet #{packetCount}. Joint Angles: [{string.Join(", ", receivedAngles)}], Gripper: {receivedGripper}%");
                            }
                            else
                            {
                                Debug.Log($"[UDP Receiver] Telemetry incoming... Packet #{packetCount}. Joint Angles: [{string.Join(", ", receivedAngles)}]");
                            }
                        }
                    }
                }
            }
            catch (Exception) { /* Passive handling */ }
        }
    }

    void Update()
    {
        float[] latestAngles = new float[6];
        float latestGripper = 0f;
        lock (lockObject)
        {
            Array.Copy(incomingPythonAngles, latestAngles, 6);
            latestGripper = incomingPythonGripper;
        }

        // Initialize active targets to incoming angles on the first received packet
        if (!isInitialized)
        {
            bool allZeros = true;
            for (int i = 0; i < 6; i++)
            {
                if (latestAngles[i] != 0.0f)
                {
                    allZeros = false;
                    break;
                }
            }
            if (allZeros && packetCount == 0) return;

            // Snap physical joint positions instantly to the first telemetry packet to prevent violent startup whips
            for (int i = 0; i < 6; i++)
            {
                if (robotJoints[i] == null) continue;

                float targetAngle = latestAngles[i];
                while (targetAngle < -180f) targetAngle += 360f;
                while (targetAngle > 180f) targetAngle -= 360f;

                robotJoints[i].jointPosition = new ArticulationReducedSpace(targetAngle * Mathf.Deg2Rad);
                activeTargets[i] = targetAngle;

                var drive = robotJoints[i].xDrive;
                drive.target = targetAngle;
                robotJoints[i].xDrive = drive;
            }

            // Snap gripper instantly on startup to match first package
            activeGripperNormalized = latestGripper / 100f;
            foreach (ArticulationBody finger in gripperJoints)
            {
                if (finger == null) continue;
                
                var drive = finger.xDrive;
                float targetAngle;
                bool isRight = IsRightSide(finger.gameObject);

                if (drive.upperLimit == 0 && drive.lowerLimit == 0)
                {
                    if (isRight)
                    {
                        targetAngle = Mathf.Lerp(gripperOpenAngle, -gripperCloseAngle, activeGripperNormalized);
                    }
                    else
                    {
                        targetAngle = Mathf.Lerp(gripperOpenAngle, gripperCloseAngle, activeGripperNormalized);
                    }
                }
                else if (isRight)
                {
                    targetAngle = Mathf.Lerp(drive.upperLimit, drive.lowerLimit, activeGripperNormalized);
                }
                else
                {
                    targetAngle = Mathf.Lerp(drive.lowerLimit, drive.upperLimit, activeGripperNormalized);
                }

                drive.target = targetAngle;
                finger.xDrive = drive;
                
                finger.jointPosition = new ArticulationReducedSpace(targetAngle * Mathf.Deg2Rad);
            }

            isInitialized = true;
            Debug.Log("[UDP Receiver] Telemetry tracking initialized and physical joints/gripper snapped smoothly to home pose.");
        }

        // Software Virtual Damping: Smoothly interpolate activeTargets towards latestAngles
        // acts as a software-level low-pass filter, fully eliminating the undamped pendulum oscillation.
        float lerpFactor = 15f * Time.deltaTime;

        for (int i = 0; i < 6; i++)
        {
            if (robotJoints[i] == null) continue;

            // Shortest angular path target mapping to prevent massive 360-degree reverse spins at wrap-arounds
            float current = activeTargets[i];
            float target = latestAngles[i];
            float delta = target - current;
            while (delta < -180f) delta += 360f;
            while (delta > 180f) delta -= 360f;

            activeTargets[i] = current + delta * Mathf.Clamp01(lerpFactor);

            var drive = robotJoints[i].xDrive;
            drive.target = activeTargets[i];
            robotJoints[i].xDrive = drive;
        }

        // Smoothly interpolate active gripper normalized state and apply to links based on their side (left/right name checks)
        float goalNormalized = latestGripper / 100f;
        activeGripperNormalized = Mathf.Lerp(activeGripperNormalized, goalNormalized, Mathf.Clamp01(lerpFactor));

        foreach (ArticulationBody finger in gripperJoints)
        {
            if (finger == null) continue;
            var drive = finger.xDrive;
            
            float targetAngle;
            bool isRight = IsRightSide(finger.gameObject);

            if (drive.upperLimit == 0 && drive.lowerLimit == 0)
            {
                if (isRight)
                {
                    targetAngle = Mathf.Lerp(gripperOpenAngle, -gripperCloseAngle, activeGripperNormalized);
                }
                else
                {
                    targetAngle = Mathf.Lerp(gripperOpenAngle, gripperCloseAngle, activeGripperNormalized);
                }
            }
            else if (isRight)
            {
                targetAngle = Mathf.Lerp(drive.upperLimit, drive.lowerLimit, activeGripperNormalized);
            }
            else
            {
                targetAngle = Mathf.Lerp(drive.lowerLimit, drive.upperLimit, activeGripperNormalized);
            }

            drive.target = targetAngle;
            finger.xDrive = drive;
        }
    }

    private bool IsRightSide(GameObject go)
    {
        if (go == null) return false;
        
        Transform current = go.transform;
        int depth = 0;
        while (current != null && depth < 5)
        {
            string name = current.name.ToLower();
            
            if (name.Contains("right")) return true;
            if (name.Contains("left")) return false;
            
            string[] tokens = name.Split('_', '-', ' ', '/');
            foreach (string token in tokens)
            {
                if (token == "r") return true;
                if (token == "l") return false;
            }
            
            current = current.parent;
            depth++;
        }
        
        return false;
    }

    void OnApplicationQuit()
    {
        isRunning = false;
        if (udpClient != null) udpClient.Close();
        if (receiveThread != null && receiveThread.IsAlive) receiveThread.Interrupt();
    }

    private void LoadConfigurations()
    {
        // Search in parent or current working directories
        string[] searchPaths = new string[] {
            System.IO.Path.Combine(Application.dataPath, "..", "config"),
            System.IO.Path.Combine(Application.dataPath, "config"),
            "config"
        };

        foreach (string dir in searchPaths)
        {
            string netPath = System.IO.Path.Combine(dir, "network_config.json");
            string robPath = System.IO.Path.Combine(dir, "robot_config.json");

            if (System.IO.File.Exists(netPath))
            {
                try
                {
                    string json = System.IO.File.ReadAllText(netPath);
                    System.Text.RegularExpressions.Match match = System.Text.RegularExpressions.Regex.Match(json, @"""udp_port""\s*:\s*(\d+)");
                    if (match.Success)
                    {
                        port = int.Parse(match.Groups[1].Value);
                        Debug.Log($"[UDP Receiver] Dynamically loaded Port from config: {port}");
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"[UDP Receiver] Failed to read network config: {e.Message}");
                }
            }

            if (System.IO.File.Exists(robPath))
            {
                try
                {
                    string json = System.IO.File.ReadAllText(robPath);
                    System.Text.RegularExpressions.Match matchOpen = System.Text.RegularExpressions.Regex.Match(json, @"""open_angle_deg""\s*:\s*([0-9.]+)");
                    if (matchOpen.Success)
                    {
                        gripperOpenAngle = float.Parse(matchOpen.Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture);
                    }
                    
                    System.Text.RegularExpressions.Match matchClosed = System.Text.RegularExpressions.Regex.Match(json, @"""closed_angle_deg""\s*:\s*([0-9.]+)");
                    if (matchClosed.Success)
                    {
                        gripperCloseAngle = float.Parse(matchClosed.Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture);
                    }
                    
                    Debug.Log($"[UDP Receiver] Dynamically loaded gripper limits: Open={gripperOpenAngle}°, Closed={gripperCloseAngle}°");
                }
                catch (Exception e)
                {
                    Debug.LogError($"[UDP Receiver] Failed to read robot config: {e.Message}");
                }
            }
        }
    }
}
