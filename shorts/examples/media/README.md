# Видео для примеров

Видео не хранится в git. Примеры `c-film-edit` и `d-long-video-clip` ищут файл `examples/media/film.mp4`
(путь в плане относительный: от папки плана).

Как получить (Big Buck Bunny, Blender Foundation, CC-BY 3.0, 640x360):

```bash
curl -L -o examples/media/film.mp4 \
  "https://archive.org/download/BigBuckBunny_124/Content/big_buck_bunny_720p_surround.mp4"
```

Подойдёт и любой свой файл: положите его сюда под именем `film.mp4`.
Без файла `validate --allow-missing-media` проходит (отсутствие файла = предупреждение), `render` честно падает.
