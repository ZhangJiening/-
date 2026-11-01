from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
assets = root / "assets"
scale, size = 4, 1024
image = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
S = lambda value: int(value * scale)
def line(points, fill, width):
    draw.line([(S(x), S(y)) for x, y in points], fill=fill, width=S(width), joint="curve")
def circle(cx, cy, radius, fill):
    draw.ellipse((S(cx-radius), S(cy-radius), S(cx+radius), S(cy+radius)), fill=fill)

line([(282,312),(512,178),(742,312),(742,630),(512,764),(282,630),(282,312)], (201,220,245,255), 34)
line([(282,312),(512,446),(742,312)], (135,181,238,255), 28)
line([(512,446),(512,764)], (135,181,238,255), 28)
line([(282,630),(512,496),(742,630)], (142,223,211,235), 28)
circle(282,312,116,(30,122,244,255)); circle(742,312,116,(30,175,165,255)); circle(512,764,116,(255,158,74,255))
circle(512,446,70,(255,255,255,255))
draw.ellipse((S(442), S(376), S(582), S(516)), outline=(30,122,244,255), width=S(24))
circle(512,446,24,(30,122,244,255)); line([(451,446),(573,446)], (30,122,244,255), 16); line([(512,385),(512,507)], (30,122,244,255), 16)
output = image.resize((size, size), Image.Resampling.LANCZOS)
output.save(assets / "logo.png", optimize=True)
output.save(assets / "app.ico", sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
print(assets / "logo.png")
print(assets / "app.ico")
