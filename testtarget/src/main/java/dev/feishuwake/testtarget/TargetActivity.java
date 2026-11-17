package dev.feishuwake.testtarget;
import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
public final class TargetActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        TextView view=new TextView(this);
        view.setText("Wake Test Target\nThis is a test fixture, NOT Feishu.");
        view.setTextSize(25); view.setPadding(30,80,30,30); setContentView(view);
    }
}
