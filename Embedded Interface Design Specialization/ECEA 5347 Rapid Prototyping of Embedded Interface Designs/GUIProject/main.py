# main.py
import sys
import time
import sqlite3
from statistics import mean
from typing import List, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGroupBox, QDoubleSpinBox, QProgressBar, QMessageBox, QDialog, QPlainTextEdit
)

from pseudo_sensor import PseudoSensor


DB_PATH = "readings.db"  # SQLite file in working directory


def fmt_ts(ts_epoch: float) -> str:
    """Return local-time string for a Unix epoch float."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_epoch))


class SensorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Humidity/Temperature Monitor – Assignment Build")
        self.resize(720, 500)

        # --- sensor & db ---
        self.sensor = PseudoSensor()
        self.conn = sqlite3.connect(DB_PATH)
        self._init_db()

        # --- labels for latest values ---
        self.h_label = QLabel("Humidity: -- %")
        self.t_label = QLabel("Temperature: -- °F")
        for lbl in (self.h_label, self.t_label):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 18px; font-weight: 600;")

        # NEW: latest timestamp label
        self.ts_label = QLabel("Last reading at: —")
        self.ts_label.setAlignment(Qt.AlignCenter)
        self.ts_label.setStyleSheet("color:#555;")

        # --- progress bars (visual feedback) ---
        self.h_bar = QProgressBar(); self.h_bar.setRange(0, 100)
        self.t_bar = QProgressBar(); self.t_bar.setRange(-20, 100); self.t_bar.setTextVisible(False)

        # --- alarm inputs (with defaults) ---
        self.h_alarm = QDoubleSpinBox()
        self.h_alarm.setRange(0.0, 100.0); self.h_alarm.setValue(85.0)  # default
        self.h_alarm.setSuffix(" %")

        self.t_alarm = QDoubleSpinBox()
        self.t_alarm.setRange(-20.0, 100.0); self.t_alarm.setValue(90.0)  # default
        self.t_alarm.setSuffix(" °F")

        # --- alarm indicator ---
        self.alarm_label = QLabel("No alarms")
        self._set_alarm_state(False)

        # --- status label (for Read 10 progress etc.) ---
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignCenter)

        # --- buttons ---
        self.btn_read_one = QPushButton("Read 1")
        self.btn_read_ten = QPushButton("Read 10 (1s apart)")
        self.btn_stats = QPushButton("Show Last 10 Stats")
        self.btn_show_last10 = QPushButton("Show Last 10 Records")
        self.btn_exit = QPushButton("Exit")

        self.btn_read_one.clicked.connect(self.read_one)
        self.btn_read_ten.clicked.connect(self.read_ten)
        self.btn_stats.clicked.connect(self.show_stats)
        self.btn_show_last10.clicked.connect(self.show_last10_records)
        self.btn_exit.clicked.connect(self.exit_app)

        # --- timer for batch reads ---
        self.batch_timer = QTimer(self)
        self.batch_timer.setInterval(1000)  # 1 second
        self.batch_timer.timeout.connect(self._batch_read_tick)
        self.batch_remaining = 0

        # --- layout ---
        top = QGroupBox("Live Readings")
        top_layout = QVBoxLayout()
        top_layout.addWidget(self.h_label)
        top_layout.addWidget(self.h_bar)
        top_layout.addWidget(self.t_label)
        top_layout.addWidget(self.t_bar)
        top_layout.addWidget(self.ts_label)  # NEW
        top.setLayout(top_layout)

        alarms = QGroupBox("Alarm Thresholds")
        alarms_layout = QHBoxLayout()
        alarms_layout.addWidget(QLabel("Humidity alarm:"))
        alarms_layout.addWidget(self.h_alarm)
        alarms_layout.addSpacing(20)
        alarms_layout.addWidget(QLabel("Temperature alarm:"))
        alarms_layout.addWidget(self.t_alarm)
        alarms_layout.addStretch()
        alarms_layout.addWidget(self.alarm_label)
        alarms.setLayout(alarms_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.btn_read_one)
        buttons_layout.addWidget(self.btn_read_ten)
        buttons_layout.addWidget(self.btn_stats)
        buttons_layout.addWidget(self.btn_show_last10)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_exit)

        root = QVBoxLayout()
        root.addWidget(top)
        root.addWidget(alarms)
        root.addLayout(buttons_layout)
        root.addWidget(self.status_label)
        self.setLayout(root)

    # ---------- DB ----------
    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                ts REAL NOT NULL,        -- unix epoch seconds
                humidity REAL NOT NULL,  -- %
                temperature REAL NOT NULL -- °F
            )
        """)
        self.conn.commit()

    def _insert_reading(self, h: float, t: float, ts: float | None = None):
        if ts is None:
            ts = time.time()
        cur = self.conn.cursor()
        cur.execute("INSERT INTO readings (ts, humidity, temperature) VALUES (?, ?, ?)",
                    (ts, float(h), float(t)))
        self.conn.commit()
        return ts  # return the ts we stored

    def _fetch_last_n(self, n: int) -> List[Tuple[float, float, float]]:
        cur = self.conn.cursor()
        cur.execute("SELECT ts, humidity, temperature FROM readings ORDER BY ts DESC LIMIT ?", (n,))
        return cur.fetchall()

    # ---------- UI helpers ----------
    def _update_latest_display(self, h: float, t: float, ts: float | None = None):
        h_clamped = max(0, min(int(h), 100))
        t_clamped = max(-20, min(int(t), 100))
        self.h_label.setText(f"Humidity: {h:.1f} %")
        self.t_label.setText(f"Temperature: {t:.1f} °F")
        self.h_bar.setValue(h_clamped)
        self.t_bar.setValue(t_clamped)

        if ts is not None:
            self.ts_label.setText(f"Last reading at: {fmt_ts(ts)}")
        self._check_alarms(h, t)

    def _check_alarms(self, h: float, t: float):
        alarm = (h > self.h_alarm.value()) or (t > self.t_alarm.value())
        self._set_alarm_state(alarm)

    def _set_alarm_state(self, alarm_on: bool):
        if alarm_on:
            self.alarm_label.setText("ALARM!")
            self.alarm_label.setStyleSheet("color: white; background:#c62828; padding:4px 8px; font-weight:700;")
        else:
            self.alarm_label.setText("No alarms")
            self.alarm_label.setStyleSheet("color: #2e7d32; background:#e8f5e9; padding:4px 8px; font-weight:600;")

    # ---------- Button actions ----------
    def read_one(self):
        """Read a single value from the pseudo sensor, store, display, alarm-check."""
        h, t = self.sensor.generate_values()
        ts = self._insert_reading(h, t)  # returns the exact timestamp used
        self._update_latest_display(h, t, ts=ts)
        self.status_label.setText("Read 1: done.")

    def read_ten(self):
        """Schedule 10 reads at 1-second intervals; store & display each."""
        if self.batch_timer.isActive():
            return  # already running
        self.batch_remaining = 10
        self.status_label.setText("Starting 10 reads...")
        self.btn_read_one.setEnabled(False)
        self.btn_read_ten.setEnabled(False)
        self.batch_timer.start()

    def _batch_read_tick(self):
        h, t = self.sensor.generate_values()
        ts = self._insert_reading(h, t)
        self._update_latest_display(h, t, ts=ts)
        self.batch_remaining -= 1
        self.status_label.setText(f"Reading batch... remaining: {self.batch_remaining}")
        if self.batch_remaining <= 0:
            self.batch_timer.stop()
            self.btn_read_one.setEnabled(True)
            self.btn_read_ten.setEnabled(True)
            self.status_label.setText("Read 10: complete.")

    def show_stats(self):
        """Compute min/max/avg over the last up to 10 readings and show on UI."""
        rows = self._fetch_last_n(10)
        if not rows:
            QMessageBox.information(self, "Stats", "No readings available yet.")
            return

        hs = [r[1] for r in rows]
        ts_vals = [r[2] for r in rows]
        newest_ts = rows[0][0]

        msg = (
            f"Stats over last {len(rows)} reading(s) (latest: {fmt_ts(newest_ts)}):\n\n"
            f"Humidity (%)\n"
            f"  Min:  {min(hs):.1f}\n"
            f"  Max:  {max(hs):.1f}\n"
            f"  Avg:  {mean(hs):.1f}\n\n"
            f"Temperature (°F)\n"
            f"  Min:  {min(ts_vals):.1f}\n"
            f"  Max:  {max(ts_vals):.1f}\n"
            f"  Avg:  {mean(ts_vals):.1f}\n"
        )
        QMessageBox.information(self, "Last 10 Stats", msg)

    def show_last10_records(self):
        """Show last up to 10 records with human-readable timestamps in a scrollable view."""
        rows = self._fetch_last_n(10)
        if not rows:
            QMessageBox.information(self, "Last 10 Records", "No readings available yet.")
            return

        # oldest -> newest for readability
        lines = []
        for ts_epoch, h, t in rows[::-1]:
            lines.append(f"{fmt_ts(ts_epoch)}  |  Hum: {h:.1f} %  |  Temp: {t:.1f} °F")

        dlg = QDialog(self)
        dlg.setWindowTitle("Last 10 Records")
        dlg.resize(520, 320)
        layout = QVBoxLayout(dlg)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText("\n".join(lines))
        layout.addWidget(view)
        ok = QPushButton("Close")
        ok.clicked.connect(dlg.accept)
        layout.addWidget(ok, alignment=Qt.AlignmentFlag.AlignRight)
        dlg.exec()

    def exit_app(self):
        """Close UI and end program."""
        try:
            self.conn.close()
        except Exception:
            pass
        self.close()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = SensorApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

