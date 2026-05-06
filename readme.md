#Using the Kinova Teach Application

1. Follow the setup instructions for the kinova robot to konfigure it inside your local network
2. Start Kinova Teach and insert the login credentials and ip address of the robot


Future Improvements:
Ist die interpolierte WaypointList deterministisch (muss getestet werden)? 
Gibt es überhaupt einen Usecase für den Cartesian Admittance Mode (da die Bewegung des Roboters hier sehr eingeschränkt ist)?
Es muss noch eine adäquate Zeitberechnung existieren und ordentlich getestet werden, welche Zeitwerte fehlschlagen (besonders bei Actions), damit hier nicht ewig während der Studie getestet werden muss. 
Audiofeedback (wann ist der Roboter bereit für die nächste Eingabe?)
Bulk-Edit von mehreren Punkten (z.B. möchte ich die Zeit von mehreren Punkten auf einmal ändern können)
Nachdem über die Software nur der vollständige Admittance Mode und nicht einzelne Joints freigegeben werden können, braucht es eine Möglichkeit, Werte einzlener Joints effizient auf einen weiteren Punkt zu übertragen, ohne bestimmte Punkte dabei anzupassen. (vielleicht machbar über das freilassen von Feldern?)
Copy - Paste - Drag-N-Drop von Punkten in der Liste?
Implementation von Greifer (sobald vorhanden) und passend zu Referenten möglicherweise auch der Einbau von einem aufgehobenen Objekt. 
Implementation einer zu den Referenten passenden Startpose welche vor Beginn des Replay angefahren wird.
Replay einer Teilsequenz der Liste soll möglich sein.
Bei Bewegung des Roboters an einen bestimmten Punkt in der Liste sollte ein ab da neu hinzugefügter Punkte hinter genau diesen Punkt in die Liste eingefügt werden.
Bei Abschluss eines Referenten muss der gesamte aktuelle UI State mit gepsiechert werden
Benötigte Logik für die Studie: 
1. csv mit Studieninfos (timestamps, wann ein neuer Referent begonnen wurde zusammen mit der PID des Teilnehmers und der Reihenfolge der Referenten. PID, ReferentID1,Timestamp1,ReferentID2,Timestamp2,...)
2. Programm soll die Eingabe der PID ermöglichen und basierend darauf (Latin Square) errechnen, in welcher Reihenfolge der Teilnehmer die Referenten angezeigt bekommt. Die UI soll auch wiedergeben, welcher Referent aktuell bearbeitet wird.
3. Visuelles Feedback? (Also Screen auf dem der Referent nachlesbar ist während der Aufgabe?)





