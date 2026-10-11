from PIL import Image

from tools.video.video_compose import VideoCompose


def test_dark_full_frame_gradient_is_not_a_matte_border(tmp_path):
    image = Image.new("RGB", (100, 60))
    for x in range(100):
        for y in range(60):
            level = 10 + y // 6
            image.putpixel((x, y), (level, level, level))
    path = tmp_path / "studio.png"
    image.save(path)
    assert not VideoCompose._detect_uniform_borders(path)["detected"]


def test_nearly_constant_encoded_matte_is_still_detected(tmp_path):
    image = Image.new("RGB", (100, 60), (60, 80, 100))
    for x in list(range(10)) + list(range(90, 100)):
        for y in range(60):
            level = (x + y) % 2
            image.putpixel((x, y), (level, level, level))
    path = tmp_path / "matte.png"
    image.save(path)
    assert VideoCompose._detect_uniform_borders(path)["pillarbox"]
