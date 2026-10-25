import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from collections import Counter
from PIL import Image, ImageChops, ImageDraw, ImageTk
from statistics import median
from zipfile import ZIP_DEFLATED, ZipFile

APP_TITLE = "LINEスタンプ画像カッター"

class StampCutter:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1080x780")
        self.root.minsize(820, 620)
        self.image = None
        self.image_path = None
        self.preview = None
        self.preview_box = (0, 0, 1, 1)
        self.render_scale = 1.0
        self.boxes = []
        self.active_box = 0
        self.drag_target = None
        self.drag_mode = tk.StringVar(value="single")
        self.selected_number = tk.StringVar(value="1")
        self.edge_var = tk.StringVar(value="左辺")
        self.step_var = tk.StringVar(value="1")
        self.zoom_var = tk.StringVar(value="100%")

        top = ttk.Frame(root, padding=12)
        top.pack(fill="x")
        ttk.Button(top, text="画像を開く…", command=self.open_image).pack(side="left")
        self.file_label = ttk.Label(top, text="PNG画像を選択してください")
        self.file_label.pack(side="left", padx=10)

        controls = ttk.LabelFrame(root, text="分割設定", padding=10)
        controls.pack(fill="x", padx=12)
        self.rows = tk.StringVar(value="4")
        self.cols = tk.StringVar(value="4")
        self.margin = tk.StringVar(value="0")
        self.gap = tk.StringVar(value="0")
        self.fit_padding = tk.StringVar(value="10")
        self._field(controls, "行数", self.rows, 0)
        self._field(controls, "列数", self.cols, 1)
        self._field(controls, "外側の余白(px)", self.margin, 2)
        self._field(controls, "コマ間隔(px)", self.gap, 3)
        self._field(controls, "自動フィット余白(px)", self.fit_padding, 4)
        ttk.Button(controls, text="均等配置に戻す", command=self.reset_layout).grid(row=0, column=5, padx=(8, 0), pady=(16, 0))
        ttk.Button(controls, text="背景を判定してフィット", command=self.auto_fit).grid(row=0, column=6, padx=(8, 0), pady=(16, 0))
        for var in (self.rows, self.cols, self.margin, self.gap):
            var.trace_add("write", lambda *_: self.reset_layout())

        modebar = ttk.Frame(root, padding=(14, 6, 14, 2))
        modebar.pack(fill="x")
        ttk.Label(modebar, text="ドラッグ:").pack(side="left")
        ttk.Radiobutton(modebar, text="選んだコマだけ", variable=self.drag_mode, value="single").pack(side="left", padx=(6, 4))
        ttk.Radiobutton(modebar, text="全コマをまとめて", variable=self.drag_mode, value="all").pack(side="left", padx=4)
        ttk.Label(modebar, text="（コマ内をクリックして選択）").pack(side="left", padx=4)

        fine = ttk.LabelFrame(root, text="ボタンで微調整", padding=(10, 6))
        fine.pack(fill="x", padx=12, pady=(2, 4))
        ttk.Label(fine, text="対象コマ").pack(side="left")
        self.select_spin = ttk.Spinbox(fine, from_=1, to=16, textvariable=self.selected_number, width=5, command=self._selection_changed)
        self.select_spin.pack(side="left", padx=(4, 12))
        self.select_spin.bind("<Return>", lambda _e: self._selection_changed())
        self.select_spin.bind("<FocusOut>", lambda _e: self._selection_changed())
        ttk.Label(fine, text="動かす辺").pack(side="left")
        self.edge_box = ttk.Combobox(fine, textvariable=self.edge_var, values=("左辺", "右辺", "上辺", "下辺"), state="readonly", width=7)
        self.edge_box.pack(side="left", padx=(4, 12))
        ttk.Label(fine, text="移動量(px)").pack(side="left")
        self.step_spin = ttk.Spinbox(fine, from_=1, to=100, textvariable=self.step_var, width=5)
        self.step_spin.pack(side="left", padx=(4, 5))
        ttk.Button(fine, text="−", width=3, command=lambda: self.nudge_edge(-1)).pack(side="left", padx=2)
        ttk.Button(fine, text="＋", width=3, command=lambda: self.nudge_edge(1)).pack(side="left", padx=2)
        ttk.Label(fine, text="表示倍率").pack(side="left", padx=(18, 0))
        self.zoom_box = ttk.Combobox(fine, textvariable=self.zoom_var, values=("100%", "150%", "200%", "300%", "400%"), state="readonly", width=7)
        self.zoom_box.pack(side="left", padx=5)
        self.zoom_box.bind("<<ComboboxSelected>>", lambda _e: self.redraw())

        status = ttk.Frame(root, padding=(14, 2, 14, 4))
        status.pack(fill="x")
        self.warning = ttk.Label(status, text="", foreground="#c00000")
        self.warning.pack(side="right")
        self.info = ttk.Label(status, text="", justify="left", anchor="w", wraplength=850)
        self.info.pack(side="left", fill="x", expand=True)

        view = ttk.Frame(root)
        view.pack(fill="both", expand=True, padx=12, pady=4)
        self.canvas = tk.Canvas(view, bg="#252525", highlightthickness=0, cursor="crosshair")
        self.hbar = ttk.Scrollbar(view, orient="horizontal", command=self.canvas.xview)
        self.vbar = ttk.Scrollbar(view, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        view.rowconfigure(0, weight=1)
        view.columnconfigure(0, weight=1)
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self.canvas.bind("<Button-1>", self.begin_drag)
        self.canvas.bind("<B1-Motion>", self.drag_line)
        self.canvas.bind("<ButtonRelease-1>", lambda _e: setattr(self, "drag_target", None))
        self.canvas.bind("<MouseWheel>", self._mousewheel)

        bottom = ttk.Frame(root, padding=12)
        bottom.pack(fill="x")
        ttk.Label(bottom, text="各コマの枠線は独立しています。ボタンは選択中のコマの辺を移動します。").pack(side="left")
        ttk.Button(bottom, text="切り出して保存…", command=self.export).pack(side="right")

    def _field(self, parent, label, var, col):
        group = ttk.Frame(parent)
        group.grid(row=0, column=col, padx=(0, 14), sticky="w")
        ttk.Label(group, text=label).pack(anchor="w")
        ttk.Spinbox(group, from_=0, to=128, textvariable=var, width=8).pack(anchor="w", pady=(3, 0))

    def _settings(self):
        rows, cols = int(self.rows.get()), int(self.cols.get())
        margin, gap = int(self.margin.get()), int(self.gap.get())
        if rows < 1 or cols < 1:
            raise ValueError("行数と列数は1以上にしてください。")
        if margin < 0 or gap < 0:
            raise ValueError("余白と間隔は0以上にしてください。")
        if self.image:
            w, h = self.image.size
            if w - 2 * margin - gap * (cols - 1) < cols or h - 2 * margin - gap * (rows - 1) < rows:
                raise ValueError("設定した余白・間隔が画像サイズに対して大きすぎます。")
        return rows, cols, margin, gap

    def _selection_changed(self):
        try:
            index = int(self.selected_number.get()) - 1
            if self.boxes:
                self.active_box = max(0, min(index, len(self.boxes) - 1))
                self.selected_number.set(str(self.active_box + 1))
                self.redraw()
        except (ValueError, tk.TclError):
            return

    def reset_layout(self):
        if self.image is not None:
            try:
                rows, cols, margin, gap = self._settings()
                w, h = self.image.size
                cell_w = (w - 2 * margin - gap * (cols - 1)) / cols
                cell_h = (h - 2 * margin - gap * (rows - 1)) / rows
                self.boxes = []
                for r in range(rows):
                    for c in range(cols):
                        left = margin + c * (cell_w + gap)
                        top = margin + r * (cell_h + gap)
                        self.boxes.append([left, top, left + cell_w, top + cell_h])
                self.active_box = 0
                self.selected_number.set("1")
                self.select_spin.configure(to=max(1, rows * cols))
            except (ValueError, tk.TclError):
                self.boxes = []
        self.redraw()

    def open_image(self):
        path = filedialog.askopenfilename(title="スタンプシートを選択", filetypes=[("画像ファイル", "*.png *.webp *.jpg *.jpeg *.bmp"), ("すべてのファイル", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as exc:
            messagebox.showerror("画像を開けません", str(exc))
            return
        self.image, self.image_path = img, Path(path)
        self.file_label.configure(text=f"{self.image_path.name}  ({img.width} × {img.height}px)")
        self.reset_layout()

    def _mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def redraw(self):
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        if self.image is None:
            self.info.configure(text="")
            return
        try:
            rows, cols, _margin, _gap = self._settings()
        except (ValueError, tk.TclError) as exc:
            self.info.configure(text=str(exc))
            self.warning.configure(text="")
            return
        if len(self.boxes) != rows * cols:
            self.info.configure(text="設定を確認してください。")
            self.warning.configure(text="")
            return
        cw, ch = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        fit = min((cw - 24) / self.image.width, (ch - 24) / self.image.height)
        zoom = int(self.zoom_var.get().replace("%", "")) / 100
        self.render_scale = max(0.01, fit * zoom)
        size = (max(1, round(self.image.width * self.render_scale)), max(1, round(self.image.height * self.render_scale)))
        self.preview = ImageTk.PhotoImage(self.image.resize(size, Image.Resampling.LANCZOS))
        x0, y0 = 0, 0
        self.preview_box = (x0, y0, size[0], size[1])
        self.canvas.create_image(x0, y0, image=self.preview, anchor="nw")
        sx = sy = self.render_scale
        oversized = False
        dim_lines = []
        for i, (x1, y1, x2, y2) in enumerate(self.boxes):
            px1, py1 = x0 + x1 * sx, y0 + y1 * sy
            px2, py2 = x0 + x2 * sx, y0 + y2 * sy
            color, width = ("#ffdc45", 3) if i == self.active_box else ("#9b9b9b", 1)
            self.canvas.create_rectangle(px1, py1, px2, py2, outline=color, width=width)
            self.canvas.create_text(px1 + 5, py1 + 4, text=str(i + 1), fill=color, anchor="nw", font=("Segoe UI", 10, "bold"))
            iw, ih = round(x2 - x1), round(y2 - y1)
            dim_lines.append(f"{i + 1}:{iw}×{ih}")
            oversized = oversized or iw > 370 or ih > 320
        self.info.configure(text=f"各コマのサイズ(px): " + "  /  ".join(dim_lines), wraplength=max(500, cw - 24))
        self.warning.configure(text="⚠ スタンプ本体の上限（370×320px）を超えるコマがあります" if oversized else "")
        self.canvas.configure(scrollregion=(0, 0, size[0], size[1]))

    def _image_point(self, event):
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        return (cx - self.preview_box[0]) / self.render_scale, (cy - self.preview_box[1]) / self.render_scale

    def begin_drag(self, event):
        if self.image is None:
            return
        ix, iy = self._image_point(event)
        sx = sy = self.render_scale
        tolerance = max(4, 9 / sx)
        candidates = []
        order = [self.active_box] + [i for i in range(len(self.boxes)) if i != self.active_box]
        for i in order:
            x1, y1, x2, y2 = self.boxes[i]
            for edge, distance in (("x1", abs(ix - x1)), ("x2", abs(ix - x2)), ("y1", abs(iy - y1)), ("y2", abs(iy - y2))):
                if distance <= tolerance:
                    candidates.append((distance * sx, 0 if i == self.active_box else 1, i, edge))
        if candidates:
            _d, _priority, i, edge = min(candidates)
            self.active_box = i
            self.selected_number.set(str(i + 1))
            self.drag_target = (i, edge)
            self.redraw()
            self.drag_line(event)
            return
        for i, (x1, y1, x2, y2) in enumerate(self.boxes):
            if x1 <= ix <= x2 and y1 <= iy <= y2:
                self.active_box = i
                self.selected_number.set(str(i + 1))
                self.drag_target = None
                self.redraw()
                return
        self.drag_target = None

    def nudge_edge(self, direction):
        if not self.boxes:
            return
        try:
            step = max(1, int(self.step_var.get())) * direction
        except ValueError:
            messagebox.showerror("移動量を確認してください", "移動量は1以上の整数を入力してください。")
            return
        box = self.boxes[self.active_box]
        edge = self.edge_var.get()
        index = {"左辺": 0, "上辺": 1, "右辺": 2, "下辺": 3}[edge]
        limit = self.image.width if index in (0, 2) else self.image.height
        other = {0: 2, 2: 0, 1: 3, 3: 1}[index]
        minimum, maximum = (0, box[other] - 1) if index in (0, 1) else (box[other] + 1, limit)
        box[index] = max(minimum, min(box[index] + step, maximum))
        self.redraw()

    def drag_line(self, event):
        if self.drag_target is None or self.image is None:
            return
        i, edge = self.drag_target
        ix, iy = self._image_point(event)
        if self.drag_mode.get() == "all":
            axis = 0 if edge.startswith("x") else 1
            target = ix if axis == 0 else iy
            old = self.boxes[i][0 if edge == "x1" else 2] if axis == 0 else self.boxes[i][1 if edge == "y1" else 3]
            delta = target - old
            limit = self.image.width if axis == 0 else self.image.height
            starts = [b[axis] for b in self.boxes]
            ends = [b[axis + 2] for b in self.boxes]
            delta = max(-min(starts), min(delta, limit - max(ends)))
            for box in self.boxes:
                box[axis] += delta
                box[axis + 2] += delta
        else:
            box = self.boxes[i]
            if edge == "x1":
                box[0] = max(0, min(round(ix), round(box[2]) - 1))
            elif edge == "x2":
                box[2] = min(self.image.width, max(round(ix), round(box[0]) + 1))
            elif edge == "y1":
                box[1] = max(0, min(round(iy), round(box[3]) - 1))
            else:
                box[3] = min(self.image.height, max(round(iy), round(box[1]) + 1))
        self.redraw()

    def _edge_checkerboard_colors(self):
        rgb = self.image.convert("RGB")
        width, height = rgb.size
        if width < 2 or height < 2:
            return None
        coords = ([(x, 0) for x in range(width)]
                  + [(width - 1, y) for y in range(1, height)]
                  + [(x, height - 1) for x in range(width - 2, -1, -1)]
                  + [(0, y) for y in range(height - 2, 0, -1)])
        pixels = [rgb.getpixel(point) for point in coords]
        quantized = [tuple((channel // 8) * 8 for channel in pixel) for pixel in pixels]
        common = Counter(quantized).most_common(2)
        if len(common) < 2:
            return None
        (color_a, count_a), (color_b, count_b) = common
        difference = max(abs(a - b) for a, b in zip(color_a, color_b))
        if difference < 24 or min(count_a, count_b) < max(4, len(pixels) * 0.06):
            return None
        categories = [0 if color == color_a else 1 if color == color_b else None for color in quantized]
        transitions = sum(
            1 for i, value in enumerate(categories)
            if value is not None and categories[(i + 1) % len(categories)] is not None
            and value != categories[(i + 1) % len(categories)]
        )
        if transitions < 4:
            return None
        return color_a, color_b

    def _foreground_mask(self):
        alpha = self.image.getchannel("A")
        alpha_min, _alpha_max = alpha.getextrema()
        checker_colors = self._edge_checkerboard_colors()

        if checker_colors:
            rgb = self.image.convert("RGB")
            backgrounds = []
            for color in checker_colors:
                reference = Image.new("RGB", rgb.size, color)
                difference = ImageChops.difference(rgb, reference)
                strongest = ImageChops.lighter(
                    ImageChops.lighter(difference.getchannel("R"), difference.getchannel("G")),
                    difference.getchannel("B"),
                )
                backgrounds.append(strongest.point(lambda value: 255 if value > 24 else 0))
            mask = ImageChops.darker(backgrounds[0], backgrounds[1])
            if alpha_min < 250:
                mask = ImageChops.darker(mask, alpha.point(lambda value: 255 if value > 8 else 0))
            return mask

        if alpha_min < 250:
            return alpha.point(lambda value: 255 if value > 8 else 0)

        rgb = self.image.convert("RGB")
        width, height = rgb.size
        border = []
        for x in range(width):
            border.append(rgb.getpixel((x, 0)))
            if height > 1:
                border.append(rgb.getpixel((x, height - 1)))
        for y in range(1, max(1, height - 1)):
            border.append(rgb.getpixel((0, y)))
            if width > 1:
                border.append(rgb.getpixel((width - 1, y)))
        background = tuple(round(median(pixel[channel] for pixel in border)) for channel in range(3))
        reference = Image.new("RGB", rgb.size, background)
        difference = ImageChops.difference(rgb, reference)
        strongest = ImageChops.lighter(
            ImageChops.lighter(difference.getchannel("R"), difference.getchannel("G")),
            difference.getchannel("B"),
        )
        return strongest.point(lambda value: 255 if value > 24 else 0)
    def _foreground_components(self, mask):
        width, height = mask.size
        foreground = mask.tobytes()
        visited = bytearray(width * height)
        components = []
        for start, value in enumerate(foreground):
            if not value or visited[start]:
                continue
            visited[start] = 1
            stack = [start]
            min_x = max_x = start % width
            min_y = max_y = start // width
            sum_x = sum_y = count = 0
            while stack:
                index = stack.pop()
                x, y = index % width, index // width
                count += 1
                sum_x += x
                sum_y += y
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
                neighbors = []
                if x > 0:
                    neighbors.append(index - 1)
                if x + 1 < width:
                    neighbors.append(index + 1)
                if y > 0:
                    neighbors.append(index - width)
                if y + 1 < height:
                    neighbors.append(index + width)
                for neighbor in neighbors:
                    if foreground[neighbor] and not visited[neighbor]:
                        visited[neighbor] = 1
                        stack.append(neighbor)
            components.append((min_x, min_y, max_x + 1, max_y + 1, sum_x / count, sum_y / count))
        return components

    def auto_fit(self):
        if self.image is None or not self.boxes:
            messagebox.showinfo("画像がありません", "先に画像を開いてください。")
            return
        try:
            rows, cols, margin, gap = self._settings()
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("設定を確認してください", str(exc))
            return

        try:
            padding = max(0, int(self.fit_padding.get()))
        except ValueError:
            messagebox.showerror("余白を確認してください", "自動フィット余白は0以上の整数を入力してください。")
            return
        # Detect foreground across the entire sheet first. The regular grid is used only to
        # associate detected pieces with a row and column, never as a crop boundary.
        mask = self._foreground_mask()
        components = self._foreground_components(mask)
        if not components:
            messagebox.showwarning("絵柄を検出できません", "背景と絵柄を判定できませんでした。枠は変更していません。")
            return

        width, height = self.image.size
        cell_w = (width - 2 * margin - gap * (cols - 1)) / cols
        cell_h = (height - 2 * margin - gap * (rows - 1)) / rows
        x_centers = [margin + c * (cell_w + gap) + cell_w / 2 for c in range(cols)]
        y_centers = [margin + r * (cell_h + gap) + cell_h / 2 for r in range(rows)]
        bounds = [None] * (rows * cols)
        for x1, y1, x2, y2, center_x, center_y in components:
            if x2 - x1 == 1 and y2 - y1 == 1:
                continue
            col = min(range(cols), key=lambda c: abs(center_x - x_centers[c]))
            row = min(range(rows), key=lambda r: abs(center_y - y_centers[r]))
            i = row * cols + col
            if bounds[i] is None:
                bounds[i] = [x1, y1, x2, y2]
            else:
                bounds[i][0] = min(bounds[i][0], x1)
                bounds[i][1] = min(bounds[i][1], y1)
                bounds[i][2] = max(bounds[i][2], x2)
                bounds[i][3] = max(bounds[i][3], y2)

        adjusted = 0
        for i, box in enumerate(bounds):
            if box is None:
                continue
            x1, y1, x2, y2 = box
            self.boxes[i] = [max(0, x1 - padding), max(0, y1 - padding), min(width, x2 + padding), min(height, y2 + padding)]
            adjusted += 1
        self.redraw()
        missing = rows * cols - adjusted
        messagebox.showinfo(
            "自動フィット完了",
            f"シート全体から絵柄を検出し、{adjusted}個の枠を余白{padding}pxで合わせました。"
            + (f"\n絵柄を検出できなかった枠: {missing}個" if missing else ""),
        )
    def _background_alpha(self):
        alpha = self.image.getchannel("A")
        alpha_min, _alpha_max = alpha.getextrema()
        checker_colors = self._edge_checkerboard_colors()
        if alpha_min < 250 and not checker_colors:
            return alpha

        # The complement of the foreground mask marks likely background pixels.
        # Flood-fill only from the image perimeter, preserving enclosed same-color details.
        background = ImageChops.invert(self._foreground_mask())
        width, height = background.size
        edge = ([(x, 0) for x in range(width)]
                + [(x, height - 1) for x in range(width)]
                + [(0, y) for y in range(1, height - 1)]
                + [(width - 1, y) for y in range(1, height - 1)])
        for point in edge:
            if background.getpixel(point) == 255:
                ImageDraw.floodfill(background, point, 128, thresh=0)
        keep = background.point(lambda value: 0 if value == 128 else 255)
        return ImageChops.darker(alpha, keep)
    def _fit_sticker_size(self, image):
        image = image.convert("RGBA")
        width, height = image.size
        scale = min(1.0, 370 / width, 320 / height)
        if scale < 1.0:
            new_size = (max(2, int(width * scale) // 2 * 2), max(2, int(height * scale) // 2 * 2))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        width, height = image.size
        even_size = (width + width % 2, height + height % 2)
        if even_size != image.size:
            padded = Image.new("RGBA", even_size, (0, 0, 0, 0))
            padded.alpha_composite(image, (0, 0))
            image = padded
        return image

    def _fixed_icon(self, content, size):
        content = content.convert("RGBA")
        content.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        position = ((size[0] - content.width) // 2, (size[1] - content.height) // 2)
        canvas.alpha_composite(content, position)
        return canvas

    def export(self):
        if self.image is None:
            messagebox.showinfo("画像がありません", "先に画像を開いてください。")
            return
        try:
            rows, cols, _margin, _gap = self._settings()
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("設定を確認してください", str(exc))
            return
        if len(self.boxes) != rows * cols:
            messagebox.showerror("設定を確認してください", "均等配置に戻してから調整してください。")
            return
        count = rows * cols
        if count not in (8, 16, 24, 32, 40):
            if not messagebox.askyesno("スタンプ数の確認", f"現在は{count}個です。LINEの静止画スタンプは8・16・24・32・40個です。\nこの個数のまま書き出しますか？"):
                return
        folder = filedialog.askdirectory(title="LINE用PNGの保存先を選択")
        if not folder:
            return

        # Apply the inferred background transparency before saving any image.
        background_alpha = self._background_alpha()
        main_content = None
        output_warnings = []
        output_paths = []
        saved = 0
        try:
            for i, (x1, y1, x2, y2) in enumerate(self.boxes):
                bounds = tuple(round(v) for v in (x1, y1, x2, y2))
                crop = self.image.crop(bounds).convert("RGBA")
                crop.putalpha(ImageChops.darker(crop.getchannel("A"), background_alpha.crop(bounds)))
                content_bounds = crop.getchannel("A").getbbox()
                if main_content is None and content_bounds:
                    main_content = crop.crop(content_bounds)
                sticker = self._fit_sticker_size(crop)
                path = Path(folder) / f"{i + 1:02d}.png"
                sticker.save(path, "PNG", dpi=(72, 72), optimize=True)
                output_paths.append(path)
                saved += 1
                if path.stat().st_size > 1024 * 1024:
                    output_warnings.append(f"{path.name} が1MBを超えています")

            if main_content is not None:
                for name, size in (("main.png", (240, 240)), ("tab.png", (96, 74))):
                    icon = self._fixed_icon(main_content.copy(), size)
                    path = Path(folder) / name
                    icon.save(path, "PNG", dpi=(72, 72), optimize=True)
                    output_paths.append(path)
                    if path.stat().st_size > 1024 * 1024:
                        output_warnings.append(f"{name} が1MBを超えています")
            else:
                output_warnings.append("絵柄を判定できず、main.png と tab.png は作成できませんでした")

            if background_alpha.getextrema()[0] == 255:
                output_warnings.append("背景を十分に判定できず、透明部分を作成できませんでした。背景色を確認してください")
            zip_path = Path(folder) / "line_stickers.zip"
            with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
                for image_path in output_paths:
                    archive.write(image_path, arcname=image_path.name)
            if zip_path.stat().st_size > 60 * 1024 * 1024:
                output_warnings.append("line_stickers.zip が公式の60MB上限を超えています")
        except Exception as exc:
            messagebox.showerror("保存に失敗しました", f"{exc}\n{saved}枚を書き出しました。")
            return

        details = [f"スタンプ画像 {saved}枚（最大370×320px・偶数サイズ）", "ZIP: line_stickers.zip（画像を直下に格納）"]
        if main_content is not None:
            details.append("main.png 240×240px、tab.png 96×74px を作成しました")
        if output_warnings:
            messagebox.showwarning("書き出しの確認", "\n".join(details + output_warnings))
        else:
            messagebox.showinfo("完了", "\n".join(details + ["PNG・72dpiで保存しました。\n" + str(folder)]))
if __name__ == "__main__":
    root = tk.Tk()
    StampCutter(root)
    root.mainloop()
