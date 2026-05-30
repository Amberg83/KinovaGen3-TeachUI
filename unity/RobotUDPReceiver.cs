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

    private UdpClient udpClient;
    private Thread receiveThread;
    private float[] incomingPythonAngles = new float[6];
    private float[] activeTargets = new float[6]; // Smoothly tracking targets
    private bool isRunning = true;
    private bool isInitialized = false;
    private int packetCount = 0;
    private readonly object lockObject = new object();

    void Start()
    {
        Debug.Log("[UDP Receiver] System initializing...");

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
                
                if (tokens != null && tokens.Length == 6)
                {
                    float[] receivedAngles = new float[6];
                    bool parseSuccess = true;
                    
                    for (int i = 0; i < 6; i++)
                    {
                        if (!float.TryParse(tokens[i], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out receivedAngles[i]))
                        {
                            parseSuccess = false;
                            break;
                        }
                    }

                    if (parseSuccess)
                    {
                        lock (lockObject)
                        {
                            Array.Copy(receivedAngles, incomingPythonAngles, 6);
                        }

                        packetCount++;
                        if (packetCount % 10 == 0)
                        {
                            Debug.Log($"[UDP Receiver] Telemetry incoming... Packet #{packetCount}. Joint Angles: [{string.Join(", ", receivedAngles)}]");
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
        lock (lockObject)
        {
            Array.Copy(incomingPythonAngles, latestAngles, 6);
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

            isInitialized = true;
            Debug.Log("[UDP Receiver] Telemetry tracking initialized and physical joints snapped smoothly to home pose.");
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
    }

    void OnApplicationQuit()
    {
        isRunning = false;
        if (udpClient != null) udpClient.Close();
        if (receiveThread != null && receiveThread.IsAlive) receiveThread.Interrupt();
    }
}
