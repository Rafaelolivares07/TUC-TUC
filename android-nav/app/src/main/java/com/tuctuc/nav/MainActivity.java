package com.tuctuc.nav;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.graphics.Color;

public class MainActivity extends Activity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER);
        layout.setPadding(48, 96, 48, 48);
        layout.setBackgroundColor(Color.parseColor("#1a1a2e"));

        // Titulo
        TextView title = new TextView(this);
        title.setText("TUC TUC Nav");
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 36);
        title.setTextColor(Color.WHITE);
        title.setGravity(Gravity.CENTER);
        layout.addView(title);

        Intent intent = getIntent();
        Uri data = intent.getData();
        String action = intent.getAction();

        if (data != null) {
            // Interceptamos un intent de navegacion!
            TextView ok = new TextView(this);
            ok.setText("Interceptacion exitosa!");
            ok.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
            ok.setTextColor(Color.parseColor("#4CAF50"));
            ok.setGravity(Gravity.CENTER);
            ok.setPadding(0, 48, 0, 32);
            layout.addView(ok);

            // Mostrar datos del intent
            TextView info = new TextView(this);
            StringBuilder sb = new StringBuilder();
            sb.append("Action: ").append(action).append("\n\n");
            sb.append("URI completa:\n").append(data.toString()).append("\n\n");
            sb.append("Scheme: ").append(data.getScheme()).append("\n");
            if (data.getHost() != null)
                sb.append("Host: ").append(data.getHost()).append("\n");
            if (data.getPath() != null && !data.getPath().isEmpty())
                sb.append("Path: ").append(data.getPath()).append("\n");
            if (data.getQuery() != null)
                sb.append("Query: ").append(data.getQuery()).append("\n");

            info.setText(sb.toString());
            info.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
            info.setTextColor(Color.parseColor("#cccccc"));
            info.setPadding(0, 16, 0, 32);
            layout.addView(info);

            // Coordenadas extraidas
            String coords = extractCoords(data);
            if (coords != null) {
                TextView coordsView = new TextView(this);
                coordsView.setText("Coordenadas: " + coords);
                coordsView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20);
                coordsView.setTextColor(Color.parseColor("#FFD700"));
                coordsView.setGravity(Gravity.CENTER);
                coordsView.setPadding(0, 0, 0, 48);
                layout.addView(coordsView);
            }
        } else {
            // Abierto desde el launcher (sin intent de navegacion)
            TextView info = new TextView(this);
            info.setText("App lista para interceptar\nintents de navegacion.\n\nCuando DiDi u otra app\nintente navegar, TUC TUC\naparecera como opcion.");
            info.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
            info.setTextColor(Color.parseColor("#aaaaaa"));
            info.setGravity(Gravity.CENTER);
            info.setPadding(0, 64, 0, 64);
            layout.addView(info);
        }

        Button closeBtn = new Button(this);
        closeBtn.setText("Cerrar");
        closeBtn.setOnClickListener(v -> finish());
        layout.addView(closeBtn);

        setContentView(layout);
    }

    private String extractCoords(Uri data) {
        if (data == null) return null;
        String uri = data.toString();

        // geo:lat,lon o geo:lat,lon?q=...
        if (uri.startsWith("geo:")) {
            String coords = uri.substring(4);
            int qIdx = coords.indexOf("?");
            if (qIdx > 0) coords = coords.substring(0, qIdx);
            if (!coords.equals("0,0") && !coords.isEmpty()) return coords;
            // Si es 0,0 buscar en parametro q
            String q = data.getQueryParameter("q");
            if (q != null) return q;
        }

        // google.navigation:q=lat,lon
        if (uri.startsWith("google.navigation:")) {
            String q = data.getQueryParameter("q");
            if (q != null) return q;
        }

        return uri;
    }
}
