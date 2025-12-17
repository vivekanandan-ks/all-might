import flet as ft
import subprocess
import threading
import shlex
import uuid
import time
from state import state


class ProcessView:
    def __init__(self, title, cmd, on_complete=None):
        self.id = str(uuid.uuid4())
        self.created_at = time.time()
        self.title = title
        self.cmd = cmd
        self.on_complete = on_complete
        self.status = "Pending"
        self.logs = []
        self.return_code = None
        self.process = None
        self.is_running = False

        # UI Controls
        self.log_view = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        self.status_text = ft.Text(
            "Pending...", color=ft.Colors.BLUE_200, weight=ft.FontWeight.BOLD
        )

        self.close_dialog_func = None

        # Buttons
        self.btn_minimize = ft.TextButton(
            "Minimize", on_click=lambda e: self.minimize()
        )
        self.btn_cancel = ft.TextButton(
            "Cancel",
            on_click=lambda e: self.cancel(),
            style=ft.ButtonStyle(color=ft.Colors.RED_400),
        )
        self.btn_close = ft.TextButton("Close", on_click=lambda e: self.minimize())

        self.action_row = ft.Row(
            alignment=ft.MainAxisAlignment.END,
            controls=[self.btn_minimize, self.btn_cancel, self.btn_close],
        )

        # Main Content Area
        self.content = ft.Container(
            width=600,
            height=400,
            content=ft.Column(
                [
                    ft.Row([self.status_text, ft.Container(expand=True)]),
                    ft.Divider(height=1, color="white24"),
                    ft.Container(
                        content=self.log_view,
                        bgcolor=ft.Colors.BLACK54,
                        border_radius=5,
                        padding=10,
                        expand=True,
                        border=ft.border.all(1, "white10"),
                    ),
                    ft.Divider(height=1, color="white24"),
                    self.action_row,
                ]
            ),
        )

        self.update_buttons()

    def update_buttons(self):
        # Update visibility based on status
        if self.is_running:
            self.btn_minimize.visible = True
            self.btn_cancel.visible = True
            self.btn_close.visible = False
        else:
            self.btn_minimize.visible = False
            self.btn_cancel.visible = False
            self.btn_close.visible = True

        if self.action_row.page:
            self.action_row.update()

    def minimize(self):
        if self.close_dialog_func:
            self.close_dialog_func()
            self.close_dialog_func = None

    def cancel(self):
        if self.process and self.is_running:
            # Immediate feedback
            self.btn_cancel.disabled = True
            self.btn_cancel.text = "Cancelling..."
            if self.action_row.page:
                self.action_row.update()

            try:
                self.process.terminate()
                msg = "Cancellation requested..."
                self.logs.append(msg)

                txt = ft.Text(msg, color="red", font_family="monospace", size=12)
                # Always append to controls so it's there when/if view is restored
                self.log_view.controls.append(txt)

                if self.log_view.page:
                    self.log_view.update()
            except Exception as e:
                print(f"Error cancelling: {e}")

    def show(self, show_dialog_func):
        self.update_buttons()
        # Pass empty actions list as we handle them internally
        self.close_dialog_func = show_dialog_func(
            self.title,
            self.content,
            [],
            dismissible=False,
        )

    def start(self):
        self.is_running = True
        self.status = "Running"
        self.status_text.value = "Running..."
        self.status_text.color = ft.Colors.BLUE_400
        self.update_buttons()

        # Register in global state
        state.add_process_view(self.id, self)

        threading.Thread(target=self._run_thread, daemon=True).start()

    def _run_thread(self):
        try:
            self.process = subprocess.Popen(
                shlex.split(self.cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            if self.process.stdout:
                for line in self.process.stdout:
                    clean_line = line.strip()
                    self.logs.append(clean_line)

                    # Update UI safely
                    if self.log_view.page:
                        self.log_view.controls.append(
                            ft.Text(clean_line, font_family="monospace", size=12)
                        )
                        self.log_view.update()
                    else:
                        self.log_view.controls.append(
                            ft.Text(clean_line, font_family="monospace", size=12)
                        )

            self.process.wait()
            self.return_code = self.process.returncode

            # Check if negative return code (signal)
            if self.return_code < 0:
                self.status = "Cancelled"
                self.status_text.value = "Cancelled"
                self.status_text.color = ft.Colors.ORANGE_400
            elif self.return_code == 0:
                self.status = "Completed"
                self.status_text.value = "Completed Successfully"
                self.status_text.color = ft.Colors.GREEN_400
                if self.on_complete:
                    try:
                        self.on_complete(True)
                    except Exception as e:
                        print(f"Error in on_complete: {e}")
            else:
                self.status = "Failed"
                self.status_text.value = f"Failed (Exit Code {self.return_code})"
                self.status_text.color = ft.Colors.RED_400
                if self.on_complete:
                    try:
                        self.on_complete(False)
                    except Exception as e:
                        print(f"Error in on_complete: {e}")

        except Exception as e:
            self.status = "Error"
            self.status_text.value = f"Error: {e}"
            self.log_view.controls.append(ft.Text(f"Error: {e}", color="red"))
            if self.on_complete:
                try:
                    self.on_complete(False)
                except Exception as ex:
                    print(f"Error in on_complete: {ex}")

        self.is_running = False
        self.update_buttons()

        # Final UI update if visible
        if self.status_text.page:
            self.status_text.update()
        if self.log_view.page:
            self.log_view.update()

        state.notify_process_update()
