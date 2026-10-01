from __future__ import annotations

import pytest
import sys
from types import SimpleNamespace

from tools.analysis.video_analyzer import VideoAnalyzer
from tools.analysis.video_downloader import VideoDownloader
from tools.base_tool import ToolResult


@pytest.fixture(autouse=True)
def forbid_caption_network_after_media_rejection(monkeypatch):
    def unexpected():
        pytest.fail('Standard analysis must stop after media rejection, before fetching captions')
    monkeypatch.setitem(sys.modules, 'youtube_transcript_api',
                        SimpleNamespace(YouTubeTranscriptApi=unexpected))


PLATFORM_URLS = [
    'https://www.douyin.com/video/7681624043124162469',
    'https://www.youtube.com/watch?v=jNQXAC9IVRw',
    'https://www.youtube.com/shorts/BGQWPY4IigY',
    'https://www.tiktok.com/@leenabhushan/video/6748451240264420610',
    'https://www.instagram.com/reel/Chunk8-jurw/',
    'https://vimeo.com/56015672',
    'https://x.com/starwars/status/665052190608723968',
    'https://www.bilibili.com/video/BV13x41117TL',
]

FAILURES = [
    ('Sign in to confirm you’re not a bot', 'CHALLENGE_REQUIRED'),
    ('Requested content is not available, rate-limit reached or login required', 'EXTRACTOR_BLOCKED'),
    ('This request has been blocked due to its TLS fingerprint', 'ACCESS_DENIED'),
    ('HTTP Error 412: Precondition Failed', 'ACCESS_DENIED'),
    ('HTTP Error 403: Forbidden', 'ACCESS_DENIED'),
    ('HTTP Error 429: Too Many Requests', 'RATE_LIMITED'),
    ('HTTP Error 404: Not Found', 'REFERENCE_UNAVAILABLE'),
    ('This video has been removed', 'REFERENCE_UNAVAILABLE'),
    ('This video is DRM protected', 'MEDIA_PROTECTED'),
    ('This video is not available in your country', 'GEO_RESTRICTED'),
    ('HTTP Error 500: Domain Not Found', 'NETWORK_UNAVAILABLE'),
    ('Login required', 'AUTH_REQUIRED'),
]


@pytest.mark.parametrize('message,kind', FAILURES)
def test_platform_failure_classification(message, kind):
    assert VideoDownloader()._classify_download_error(message) == kind


@pytest.mark.parametrize('url', PLATFORM_URLS)
@pytest.mark.parametrize('message,kind', FAILURES)
def test_analyzer_preserves_failure_and_does_not_retry_or_fake_analysis(tmp_path, monkeypatch, url, message, kind):
    calls = []
    def unavailable(_self, inputs):
        calls.append(inputs)
        return ToolResult(success=False, error=message,
                          data={'error_kind':kind, 'storage_state_source':'none'})
    monkeypatch.setattr(VideoDownloader, 'execute', unavailable)
    result = VideoAnalyzer().execute({'source':url,'analysis_depth':'standard',
                                     'output_dir':str(tmp_path)})
    assert not result.success
    assert result.data['source']['download_error_kind'] == kind
    assert result.data['source']['duration_seconds'] == 0
    assert result.data.get('keyframes', []) == []
    assert len(calls) == 1


@pytest.mark.parametrize('message,kind', [f for f in FAILURES if f[1] != 'EXTRACTOR_BLOCKED'])
def test_metadata_rejection_stops_before_repeating_media_request(tmp_path, monkeypatch, message, kind):
    downloader = VideoDownloader()
    monkeypatch.setattr(downloader, '_resolve_storage_state_path', lambda *_a: (None,'none'))
    monkeypatch.setattr(downloader, '_extract_metadata', lambda *_a: {'error':message,'duration':0})
    def unexpected(*_a):
        pytest.fail('Terminal rejection must not trigger the same media request')
    monkeypatch.setattr(downloader, '_download_video', unexpected)
    result = downloader.execute({'url':PLATFORM_URLS[1],'output_dir':str(tmp_path)})
    assert not result.success
    assert result.data['error_kind'] == kind


@pytest.mark.parametrize('mode,returned', [('video',(None,None)),('audio_only',None),('subtitles_only',None)])
def test_downloader_requires_requested_artifact(tmp_path, monkeypatch, mode, returned):
    downloader = VideoDownloader()
    monkeypatch.setattr(downloader,'_extract_metadata',lambda *_a:{'duration':12,'title':'Reference'})
    method = {'video':'_download_video','audio_only':'_download_audio','subtitles_only':'_download_subtitles'}[mode]
    monkeypatch.setattr(downloader,method,lambda *_a:returned)
    result = downloader.execute({'url':PLATFORM_URLS[1],'output_dir':str(tmp_path),'format':mode})
    assert not result.success
    assert result.data['error_kind'] == 'REFERENCE_MEDIA_UNAVAILABLE'


def test_downloader_rejects_corrupt_video_even_with_good_remote_metadata(tmp_path, monkeypatch):
    video = tmp_path/'reference_video.mp4'
    video.write_bytes(b'not a media file')
    downloader = VideoDownloader()
    monkeypatch.setattr(downloader,'_extract_metadata',lambda *_a:{'duration':12,'title':'Reference'})
    monkeypatch.setattr(downloader,'_download_video',lambda *_a:(str(video),None))
    result = downloader.execute({'url':PLATFORM_URLS[1],'output_dir':str(tmp_path)})
    assert not result.success
    assert result.data['error_kind'] == 'INVALID_REFERENCE_MEDIA'


@pytest.mark.parametrize('url', PLATFORM_URLS)
def test_invalid_authorized_state_stops_before_any_platform_request(tmp_path, monkeypatch, url):
    downloader = VideoDownloader()
    def unexpected(*_a):
        pytest.fail('Invalid state must be rejected before contacting the platform')
    monkeypatch.setattr(downloader, '_extract_metadata', unexpected)
    result = downloader.execute({'url':url,'output_dir':str(tmp_path),
                                 'playwright_storage_state_path':str(tmp_path/'missing-state.json')})
    assert not result.success
    assert result.data['error_kind'] == 'INVALID_STORAGE_STATE'


def test_subtitle_rejection_preserves_auth_failure(tmp_path, monkeypatch):
    downloader = VideoDownloader()
    monkeypatch.setattr(downloader, '_extract_metadata', lambda *_a: {'duration':12})
    def rejected(*_a):
        raise RuntimeError('Login required')
    monkeypatch.setattr(downloader, '_download_with_background_retry', rejected)
    result = downloader.execute({'url':PLATFORM_URLS[1],'output_dir':str(tmp_path),'format':'subtitles_only'})
    assert not result.success
    assert result.data['error_kind'] == 'AUTH_REQUIRED'


def test_transcript_only_does_not_succeed_without_a_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(VideoDownloader, 'execute', lambda *_a: ToolResult(
        success=False, error='Verification challenge required', data={'error_kind':'CHALLENGE_REQUIRED'}))
    result = VideoAnalyzer().execute({'source':PLATFORM_URLS[0],'analysis_depth':'transcript_only',
                                     'output_dir':str(tmp_path)})
    assert not result.success
    assert not result.data.get('narration_transcript',{}).get('full_text')


def test_valid_youtube_captions_still_complete_transcript_only(tmp_path, monkeypatch):
    from tools.analysis.transcript_fetcher import TranscriptFetcher
    monkeypatch.setitem(sys.modules, 'youtube_transcript_api', SimpleNamespace(
        YouTubeTranscriptApi=lambda: SimpleNamespace(list=lambda *_a: [])))
    monkeypatch.setattr(VideoDownloader, 'execute', lambda *_a: ToolResult(
        success=True, data={'metadata':{'duration':19,'title':'Reference'}}))
    monkeypatch.setattr(TranscriptFetcher, 'execute', lambda *_a: ToolResult(
        success=True, data={'full_text':'Here we are in front of the elephants.',
                           'transcript':[], 'language':'en'}))
    result = VideoAnalyzer().execute({'source':PLATFORM_URLS[1],'analysis_depth':'transcript_only',
                                     'output_dir':str(tmp_path)})
    assert result.success
    assert result.data['narration_transcript']['full_text']


def test_short_preview_is_not_accepted_as_full_reference(tmp_path, monkeypatch):
    video = tmp_path/'reference_video.mp4'
    video.write_bytes(b'downloaded preview')
    downloader = VideoDownloader()
    monkeypatch.setattr(downloader,'_extract_metadata',lambda *_a:{'duration':553.82})
    monkeypatch.setattr(downloader,'_download_video',lambda *_a:(str(video),None))
    monkeypatch.setattr(downloader,'_probe_local_media',lambda *_a:{'duration':30,'resolution':'640x360'})
    result = downloader.execute({'url':PLATFORM_URLS[-1],'output_dir':str(tmp_path)})
    assert not result.success
    assert result.data['error_kind'] == 'INCOMPLETE_REFERENCE_MEDIA'
