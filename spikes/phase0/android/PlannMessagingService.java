// PHASE 0 SPIKE (S5) — throwaway. Deprioritised: only gates the post-MVP Android ongoing notification.
// Place in frontend/android/app/src/main/java/co/plannapp/app/PlannMessagingService.java
//
// AndroidManifest.xml (inside <application>, root needs xmlns:tools="http://schemas.android.com/tools"):
//   <service android:name="com.capacitorjs.plugins.pushnotifications.MessagingService" tools:node="remove" />
//   <service android:name=".PlannMessagingService" android:exported="false">
//       <intent-filter><action android:name="com.google.firebase.MESSAGING_EVENT" /></intent-filter>
//   </service>
//
// Pass criteria: (1) existing JS 'pushNotificationReceived' still fires in foreground,
// (2) a data-only message with plann_kind=la_spike posts the ongoing chronometer notification
//     while the app is backgrounded AND after it was swiped away, (3) token refresh still reaches JS.
package co.plannapp.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.os.Build;
import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import com.capacitorjs.plugins.pushnotifications.MessagingService;
import com.google.firebase.messaging.RemoteMessage;
import java.util.Map;

public class PlannMessagingService extends MessagingService {
    private static final String CHANNEL = "plann_spike_ongoing";

    @Override
    public void onMessageReceived(@NonNull RemoteMessage remoteMessage) {
        super.onMessageReceived(remoteMessage); // keeps Capacitor JS delivery intact
        Map<String, String> d = remoteMessage.getData();
        if (!"la_spike".equals(d.get("plann_kind"))) return;

        NotificationManager nm = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= 26 && nm.getNotificationChannel(CHANNEL) == null) {
            nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Spike ongoing", NotificationManager.IMPORTANCE_DEFAULT));
        }
        long startMs = Long.parseLong(d.getOrDefault("start_ms", String.valueOf(System.currentTimeMillis())));
        NotificationCompat.Builder b = new NotificationCompat.Builder(this, CHANNEL)
                .setSmallIcon(getApplicationInfo().icon)
                .setContentTitle(d.getOrDefault("title", "İşlemde"))
                .setContentText(d.getOrDefault("body", "Spike"))
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setUsesChronometer(true)
                .setWhen(startMs);
        try {
            NotificationManagerCompat.from(this).notify(d.getOrDefault("apt", "spike").hashCode(), b.build());
        } catch (SecurityException ignored) {
            // POST_NOTIFICATIONS denied on API 33+: record as a result, do not crash
        }
    }
}
