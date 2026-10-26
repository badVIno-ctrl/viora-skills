"""Animated bottom ad panel (v3.6 layout). QR is a constant integer-module bitmap, never animated.

Layout rules (reference/ad-banner-standard.md): one message, one action, strict grid, content block
centred vertically, nothing touches an edge, disclosure always visible, text auto-fitted (never
shrunk below a readable size - the label must be shortened instead), CTA colour picked by contrast.
Public API unchanged: AnimatedBanner(w, h, brand, cfg, logo)(t) -> RGBA image, .manifest().
Colours: variant quattro / bob keep their palettes; cfg["colors"] = {bg, accent, fg} overrides.
"""
from __future__ import annotations
import io
from PIL import Image, ImageDraw, ImageFont
import segno

SS = 4  # supersampling for shapes


def keyframe(keys, t):
    if not keys:
        return 1.0
    if t <= keys[0]['t']:
        return float(keys[0]['value'])
    for a, b in zip(keys, keys[1:]):
        if t <= b['t']:
            u = (t-a['t'])/max(1e-9, b['t']-a['t'])
            mode = b.get('ease', 'out_cubic')
            u = 1-(1-u)**3 if mode == 'out_cubic' else u*u*(3-2*u) if mode == 'in_out' else u
            return a['value']+(b['value']-a['value'])*u
    return float(keys[-1]['value'])


def track(delay, enter=.65):
    return [{'t': delay, 'value': 0}, {'t': delay+enter, 'value': 1, 'ease': 'out_cubic'}]


def _rgb(c):
    if isinstance(c, tuple):
        return c[:3]
    c = c.lstrip('#')
    if len(c) == 3:
        c = ''.join(ch*2 for ch in c)
    return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))


def _lum(c):
    def f(v):
        v /= 255
        return v/12.92 if v <= .03928 else ((v+.055)/1.055)**2.4
    r, g, b = (f(x) for x in _rgb(c))
    return .2126*r+.7152*g+.0722*b


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi+.05)/(lo+.05)


def readable_on(bg, light='#FFFFFF', dark='#0B0F14'):
    return light if contrast(bg, light) >= contrast(bg, dark) else dark


def rrect(w, h, r, fill):
    im = Image.new('RGBA', (w*SS, h*SS), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w*SS-1, h*SS-1), radius=r*SS, fill=fill)
    return im.resize((w, h), Image.LANCZOS)


def with_alpha(im, v):
    im = im.copy()
    im.putalpha(im.getchannel('A').point(lambda x: int(x*max(0, min(1, v)))))
    return im


class AnimatedBanner:
    PAD = 40
    def __init__(self, w, h, brand, cfg, logo=None):
        if w < 480 or h < 240:
            raise ValueError('Animated banner needs >=480x240; reduce content instead of unreadable microtype')
        self.w, self.h, self.brand, self.cfg = w, h, brand, cfg
        a = cfg.get('animation') or {}
        self.cycle = float(a.get('cycle', 12)); self.variant = a.get('variant', 'quattro')
        if self.cycle < 8:
            raise ValueError('Cycle must allow a readable quiet QR hold')
        self.tracks = {'logo': track(0, .75), 'title': track(.35, .75), 'message': track(1.1, .5),
                       'cta': track(2.7, .55), 'accent': track(3.4, .8)}
        self.tracks.update(a.get('tracks') or {})
        for keys in self.tracks.values():
            if not keys or any(y['t'] <= x['t'] for x, y in zip(keys, keys[1:])):
                raise ValueError('Keyframe times must increase')
        col = cfg.get('colors') or {}
        self.bg = _rgb(col.get('bg') or ('#101419' if self.variant == 'quattro' else '#131B2B'))
        self.accent = _rgb(col.get('accent') or ('#EE4B4F' if self.variant == 'quattro' else '#66D9D2'))
        self.fg = _rgb(col.get('fg') or '#FFFFFF')
        self.k = max(.65, min(1.4, h/384))
        self.logo = None
        if logo:
            self.logo = Image.open(logo).convert('RGBA')
        self.url = cfg.get('qr_url', ''); self.qr = None; self.qr_box = None
        if self.url:
            qr = segno.make(self.url, error='m', micro=False)
            modules = qr.symbol_size(scale=1, border=4)[0]
            scale = min((h-40)//modules, (w//3)//modules)
            if scale < 3:
                raise ValueError('QR too small: increase panel height, do not resample modules')
            f = io.BytesIO(); qr.save(f, kind='png', scale=scale, border=4, dark='black', light='white'); f.seek(0)
            self.qr = Image.open(f).convert('RGBA')
            self.qr_box = (w-self.qr.width-int(a.get('safe_right', 40)), (h-self.qr.height)//2, self.qr.width, self.qr.height)
        self.rois = {}
        self._static = None
        self._build()

    # ------------------------------------------------------------------ static geometry
    def _font(self, path, size):
        return ImageFont.truetype(str(path), int(size))

    def _fit(self, label, path, size, min_size, width, lines=1):
        """Largest size in [min_size, size] that fits; wraps to `lines` lines only at the end. Never below min_size."""
        size = int(size)
        while size >= min_size:
            f = self._font(path, size)
            if f.getlength(label) <= width:
                return f, [label]
            size -= 1
        f = self._font(path, min_size)
        if lines > 1:
            words, rows, cur = label.split(), [], ''
            for wd in words:
                t = (cur+' '+wd).strip()
                if f.getlength(t) <= width or not cur:
                    cur = t
                else:
                    rows.append(cur); cur = wd
            rows.append(cur)
            if len(rows) <= lines and all(f.getlength(r) <= width for r in rows):
                return f, rows
        raise ValueError(f'Banner label too long for the panel: "{label}" - shorten it (min readable size {min_size}px)')

    def _build(self):
        w, h, k, pad = self.w, self.h, self.k, self.PAD
        font, bold = self.brand.body.path, self.brand.display.path
        right = (self.qr_box[0]-int(32*k)) if self.qr_box else w-pad
        self.right = right
        # --- rows
        tile = int(112*k); gap = int(24*k); btn_h = int(76*k); gap2 = int(10*k); gap3 = int(6*k)
        tx = pad+tile+int(24*k)
        name = self.cfg.get('name') or self.brand.logo_text or self.cfg.get('handle', 'VPN')
        self.defaults_used = []
        msg = self.cfg.get('message') or self.cfg.get('tagline') or ''
        if not msg:  # legacy plans only; new work must set message/action (manifest flags it)
            msg = 'VPN в Telegram'; self.defaults_used.append('message')
        tw = right-tx
        self.f_name, name_rows = self._fit(name, bold, 52*k, 34, tw)
        self.f_msg, msg_rows = self._fit(msg, font, 34*k, 26, tw, lines=2)
        def lh(f): return f.getbbox('Ag')[3]-f.getbbox('Ag')[1]
        n_h, m_h = lh(self.f_name), lh(self.f_msg)
        msg_h = m_h*len(msg_rows)+gap3*(len(msg_rows)-1)
        # --- CTA button + handle
        cta = self.cfg.get('action') or ''
        if not cta:
            cta = 'Открыть бота'; self.defaults_used.append('action')
        f_cta = self._font(bold, 34*k)
        arrow_w = int(34*k)
        bw = int(f_cta.getlength(cta))+int(36*k)*2+arrow_w+int(14*k)
        if pad+bw > right:
            raise ValueError('CTA button does not fit: shorten the action text')
        handle = self.cfg.get('handle', '')
        handle = ('@'+handle.lstrip('@')) if handle else ''
        self.handle = handle
        hx = pad+bw+int(24*k)
        handle_in_stack = False
        if handle:
            try:
                self.f_handle, _ = self._fit(handle, font, 34*k, 26, right-hx)
            except ValueError:  # no room next to the button: third line in the text stack instead of microtype
                handle_in_stack = True
                self.f_handle, _ = self._fit(handle, font, 30*k, 24, tw)
        h_h = lh(self.f_handle) if handle else 0
        stack_h = n_h+gap2+msg_h+((gap3+h_h) if handle_in_stack else 0)
        row_h = max(tile, stack_h)
        block_h = row_h+gap+btn_h
        top = 4+max(int(60*k), (h-4-block_h)//2)
        self.tile_box = (pad, top+(row_h-tile)//2, tile, tile)
        sy = top+(row_h-stack_h)//2
        self.name_xy = (tx, sy, tw, n_h, name_rows[0])
        self.msg_xy = (tx, sy+n_h+gap2, tw, msg_h, msg_rows, m_h)
        by = top+row_h+gap
        self.btn_box = (pad, by, bw, btn_h)
        if handle:
            if handle_in_stack:
                self.handle_box = (tx, sy+n_h+gap2+msg_h+gap3, tw, h_h)
            else:
                self.handle_box = (hx, by, right-hx, btn_h)
        self.f_cta, self.cta_text = f_cta, cta
        self.btn_fill = self.accent
        self.btn_ink = _rgb(readable_on(self.accent))
        # --- copy lint (heuristics from reference/ad-banner-standard.md, [Г])
        self.warnings = []
        if len(msg.split()) > 7:
            self.warnings.append('message longer than 7 words: shorten to one benefit')
        if len(cta.split()) > 4:
            self.warnings.append('action longer than 4 words')
        risky = ('бесплатно', 'скидк', 'лучший', 'без комисси', 'гарант', 'быстр', 'безопасн', 'free', 'best', 'guarantee')
        if not self.cfg.get('claims_verified'):
            hit = [r for r in risky if r in (msg+' '+cta+' '+name).lower()]
            if hit:
                self.warnings.append('risky claim words without claims_verified: '+', '.join(hit))
        if self.btn_ink and contrast(self.btn_fill, self.btn_ink) < 4.5:
            self.warnings.append('CTA contrast below 4.5')
        # --- disclosure
        label = self.cfg.get('disclosure_label', 'РЕКЛАМА')
        f_d = self._font(bold, int(24*k))
        self.f_dis, self.dis_text = f_d, label
        dw = int(f_d.getlength(label))+int(24*k)
        self.dis_box = (pad, 4+int(18*k), dw, int(36*k))
        if self.dis_box[1]+self.dis_box[3] > top-int(8*k):
            raise ValueError('Panel too short for disclosure + content block')
        # --- tile (logo or typographic monogram)
        self.tile_img = self._make_tile(tile)
        # --- ROIs (always complete, even before the CTA appears)
        self.rois = {'logo': self.tile_box, 'title': (tx, sy, tw, n_h), 'message': (tx, self.msg_xy[1], tw, self.msg_xy[3]),
                     'cta': self.btn_box, 'disclosure': self.dis_box}
        if handle:
            self.rois['handle'] = self.handle_box
        # --- static layer (bg, rule, disclosure, handle, QR)
        im = Image.new('RGBA', (w, h), self.bg+(255,)); d = ImageDraw.Draw(im)
        d.rectangle((0, 0, w-1, 3), fill=self.accent)
        im.alpha_composite(self._disclosure(), self.dis_box[:2])
        if self.variant == 'bob' and not self.cfg.get('colors'):
            d.rectangle((16, 4+int(24*k), 20, h-int(24*k)), fill=self.accent)
        if self.qr:
            im.alpha_composite(self.qr, self.qr_box[:2])
        self._static = im

    def _make_tile(self, s):
        if self.logo:
            lg = self.logo.copy(); lg.thumbnail((s, s), Image.LANCZOS)
            t = Image.new('RGBA', (s, s), (0, 0, 0, 0))
            t.alpha_composite(lg, ((s-lg.width)//2, (s-lg.height)//2))
            mask = rrect(s, s, int(s*.2), (255, 255, 255, 255)).getchannel('A')
            a = t.getchannel('A'); from PIL import ImageChops
            t.putalpha(ImageChops.multiply(a, mask))
            return t
        # honest typographic monogram - not an official mark
        t = rrect(s, s, int(s*.2), self.accent+(255,))
        name = (self.cfg.get('name') or self.cfg.get('handle') or 'V').lstrip('@')
        d = ImageDraw.Draw(t)
        d.text((s//2, s//2), name[:1].upper(), font=self._font(self.brand.display.path, int(s*.55)), fill=self.btn_ink, anchor='mm')
        return t

    def _disclosure(self):
        x, y, bw, bh = self.dis_box
        pill = rrect(bw, bh, int(bh*.3), (0, 0, 0, 0))
        big = Image.new('RGBA', (bw*SS, bh*SS), (0, 0, 0, 0))
        ImageDraw.Draw(big).rounded_rectangle((0, 0, bw*SS-1, bh*SS-1), radius=int(bh*.3)*SS, outline=self.fg+(200,), width=2*SS)
        pill = big.resize((bw, bh), Image.LANCZOS)
        ImageDraw.Draw(pill).text((bw//2, bh//2), self.dis_text, font=self.f_dis, fill=self.fg+(235,), anchor='mm')
        return pill

    # ------------------------------------------------------------------ frames
    def manifest(self):
        return {'cycle': self.cycle, 'variant': self.variant, 'tracks': self.tracks, 'qr_url': self.url, 'qr_box': self.qr_box,
                'quiet_phase': [4.3, self.cycle-.5], 'logo_provenance': 'provided asset' if self.logo else 'typographic, not official logo',
                'requires_final_mp4_qr_decode': bool(self.qr), 'element_boxes': self.rois,
                'layout': 'v3.6', 'cta_contrast': round(contrast(self.btn_fill, self.btn_ink), 2),
                'disclosure': self.dis_text, 'defaults_used': self.defaults_used, 'warnings': self.warnings}

    def __call__(self, t):
        t = t % self.cycle
        im = self._static.copy(); k = self.k
        # logo tile: fade + slide from the left
        v = keyframe(self.tracks['logo'], t)
        x, y, s, _ = self.tile_box
        im.alpha_composite(with_alpha(self.tile_img, v), (x+int(48*(1-v)), y))
        # title: reveal by mask
        v = keyframe(self.tracks['title'], t)
        x, y, tw, nh, label = self.name_xy
        layer = Image.new('RGBA', (tw, nh+int(14*k)), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((0, nh), label, font=self.f_name, fill=self.fg, anchor='ls')
        layer = layer.crop((0, 0, max(1, int(layer.width*v)), layer.height))
        im.alpha_composite(layer, (x, y-int(3*k)))
        # message: fade + slide up
        v = keyframe(self.tracks['message'], t)
        x, y, tw, mh, rows, lh_ = self.msg_xy
        layer = Image.new('RGBA', (tw, mh+int(14*k)), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
        for i, r in enumerate(rows):
            ld.text((0, lh_*(i+1)+int(6*k)*i), r, font=self.f_msg, fill=self.fg+(215,), anchor='ls')
        im.alpha_composite(with_alpha(layer, v), (x, y-int(3*k)+int(14*(1-v))))
        # CTA button: appears once, then still; one short shine
        v = keyframe(self.tracks['cta'], t)
        if v > 0:
            bx, by, bw, bh = self.btn_box
            btn = rrect(bw, bh, bh//2, self.btn_fill+(255,))
            d = ImageDraw.Draw(btn)
            d.text((int(36*k), bh//2), self.cta_text, font=self.f_cta, fill=self.btn_ink, anchor='lm')
            ax = bw-int(36*k)-int(34*k); ay = bh//2; L = int(30*k); wd = max(3, int(4*k))
            d.line((ax, ay, ax+L, ay), fill=self.btn_ink, width=wd)
            d.line((ax+L-int(12*k), ay-int(12*k), ax+L, ay), fill=self.btn_ink, width=wd)
            d.line((ax+L-int(12*k), ay+int(12*k), ax+L, ay), fill=self.btn_ink, width=wd)
            sv = keyframe(self.tracks['accent'], t)
            if 3.4 < t < 4.3:
                sx = int(-bh+(bw+2*bh)*sv)
                shine = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
                ImageDraw.Draw(shine).polygon([(sx, bh), (sx+bh//2, 0), (sx+bh//2+int(28*k), 0), (sx+int(28*k), bh)], fill=(255, 255, 255, 70))
                from PIL import ImageChops
                shine.putalpha(ImageChops.multiply(shine.getchannel('A'), btn.getchannel('A')))
                btn.alpha_composite(shine)
            im.alpha_composite(with_alpha(btn, v), (bx, by+int(18*(1-v))))
            if self.handle:
                hx, hy, hw, hh = self.rois['handle']
                layer = Image.new('RGBA', (hw, hh), (0, 0, 0, 0))
                ImageDraw.Draw(layer).text((0, hh//2), self.handle, font=self.f_handle, fill=self.fg, anchor='lm')
                im.alpha_composite(with_alpha(layer, v), (hx, hy+int(18*(1-v))))
        return im
