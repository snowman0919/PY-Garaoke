import numpy as np
import librosa
import librosa.display
import os
import random

class KaraokeScorer:

    def __init__(self, sr=22050, hop_length=512):
        self.sr = sr
        self.hop_length = hop_length

    def get_pitch_contour(self, audio_path, save_path=None):
        if save_path and os.path.exists(save_path):
            try:
                f0_interp = np.load(save_path)
                return f0_interp
            except Exception as e:
                print(f"Failed to load cached pitch from {save_path}: {e}")
        analysis_sr = 8000
        y, sr = librosa.load(audio_path, sr=analysis_sr)
        hop_length_low = int(self.hop_length * (analysis_sr / self.sr))
        if hop_length_low < 64: hop_length_low = 64
        f0, _, _ = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=sr, hop_length=hop_length_low)
        times_low = librosa.times_like(f0, sr=sr, hop_length=hop_length_low)
        times_orig = np.arange(0, len(y)/sr, self.hop_length/self.sr)
        f0_interp = np.interp(times_orig, times_low, f0, left=np.nan, right=np.nan)
        if save_path:
            try:
                np.save(save_path, f0_interp)
            except Exception as e:
                print(f"Failed to save pitch cache to {save_path}: {e}")
        return f0_interp

    def load_audio_for_scoring(self, audio_path):
        analysis_sr = 8000
        y, sr = librosa.load(audio_path, sr=analysis_sr)
        return y, sr

    def _quantize_pitch_to_notes(self, f0):
        midi_notes = librosa.hz_to_midi(f0)
        valid_midi = midi_notes[~np.isnan(midi_notes)]
        quantized_midi = np.round(valid_midi)
        return quantized_midi

    def _calculate_pitch_accuracy(self, user_f0, ref_f0, tolerance_cents=50):
        min_len = min(len(user_f0), len(ref_f0))
        user_f0_trimmed = user_f0[:min_len]
        ref_f0_trimmed = ref_f0[:min_len]

        valid_indices = np.where(~np.isnan(ref_f0_trimmed) & (ref_f0_trimmed > 0))[0]
        if len(valid_indices) == 0:
            return 0.0

        window_size = 5
        
        total_score = 0.0
        valid_frame_count = 0

        for idx in valid_indices:
            ref_val = ref_f0_trimmed[idx]
            
            start_w = max(0, idx - window_size)
            end_w = min(len(user_f0_trimmed), idx + window_size + 1)
            
            user_window = user_f0_trimmed[start_w:end_w]
            
            valid_user_window = user_window[~np.isnan(user_window) & (user_window > 0)]
            
            if len(valid_user_window) == 0:
                continue
            
            with np.errstate(divide='ignore', invalid='ignore'):
                cents_diffs = np.abs(1200 * np.log2(valid_user_window / ref_val))
            
            min_diff = np.min(cents_diffs)
            
            if min_diff < tolerance_cents:
                total_score += 1.0
            elif min_diff < (tolerance_cents + 50):
                total_score += 0.5
            
        return (total_score / len(valid_indices)) * 100

    def _calculate_rhythm_accuracy(self, user_y, user_sr, ref_y, ref_sr, tolerance_frames=3):
        user_onsets = librosa.onset.onset_detect(y=user_y, sr=user_sr, hop_length=self.hop_length)
        ref_onsets = librosa.onset.onset_detect(y=ref_y, sr=ref_sr, hop_length=self.hop_length)
        user_onset_frames = user_onsets
        ref_onset_frames = ref_onsets
        if len(ref_onset_frames) == 0:
            return 100.0
        matched_onsets = 0
        used_user_onsets = np.zeros_like(user_onset_frames, dtype=bool)
        for ref_frame in ref_onset_frames:
            distances = np.abs(user_onset_frames - ref_frame)
            if len(distances) == 0:
                continue
            closest_user_idx = np.argmin(distances)
            if not used_user_onsets[closest_user_idx] and distances[closest_user_idx] < tolerance_frames:
                matched_onsets += 1
                used_user_onsets[closest_user_idx] = True
        score = (matched_onsets / len(ref_onset_frames)) if len(ref_onset_frames) > 0 else 0
        return score * 100

    def _calculate_vibrato_quality(self, user_f0, ref_f0, min_vibrato_hz=2, max_vibrato_hz=8, min_duration_sec=0.3):
        ref_valid_mask = ~np.isnan(ref_f0) & (ref_f0 > 0)
        if not np.any(ref_valid_mask):
            return 0.0

        min_frames = int(self.sr * min_duration_sec / self.hop_length)
        
        segments = []
        current_segment = []
        
        for i, val in enumerate(ref_f0):
            if np.isnan(val) or val <= 0:
                if len(current_segment) >= min_frames:
                    segments.append(current_segment)
                current_segment = []
                continue
            
            if current_segment:
                prev_val = ref_f0[current_segment[-1]]
                if abs(1200 * np.log2(val / prev_val)) > 50:
                    if len(current_segment) >= min_frames:
                        segments.append(current_segment)
                    current_segment = []
            
            current_segment.append(i)
            
        if len(current_segment) >= min_frames:
            segments.append(current_segment)

        if not segments:
            return 0.0

        segment_scores = []
        
        for seg_indices in segments:
            user_seg_vals = []
            valid_count = 0
            
            for idx in seg_indices:
                if idx < len(user_f0):
                    u_val = user_f0[idx]
                    if not np.isnan(u_val) and u_val > 0:
                        user_seg_vals.append(u_val)
                        valid_count += 1
                    else:
                        user_seg_vals.append(np.nan)
                else:
                    user_seg_vals.append(np.nan)
            
            if valid_count < (len(seg_indices) * 0.5):
                segment_scores.append(0.0)
                continue

            valid_vals = [v for v in user_seg_vals if not np.isnan(v)]
            if len(valid_vals) < 2:
                segment_scores.append(0.0)
                continue
                
            center = np.mean(valid_vals)
            cents_deviation = 1200 * np.log2(np.array(valid_vals) / center)
            std_dev_cents = np.std(cents_deviation)
            
            user_segment_std = np.std(valid_vals)

            if user_segment_std > min_vibrato_hz and user_segment_std < max_vibrato_hz:
                segment_scores.append(100.0)
            elif user_segment_std >= max_vibrato_hz:
                segment_scores.append(40.0)
            elif user_segment_std <= min_vibrato_hz and user_segment_std > 0.1:
                segment_scores.append(70.0)
            else:
                segment_scores.append(20.0)

        if not segment_scores:
            return 0.0
            
        return sum(segment_scores) / len(segment_scores)

    def score_performance(self, user_take_path, reference_sr_path, ref_pitch_cache_path=None):
        user_f0 = self.get_pitch_contour(user_take_path)
        ref_f0 = self.get_pitch_contour(reference_sr_path, save_path=ref_pitch_cache_path)
        user_y, user_sr = self.load_audio_for_scoring(user_take_path)
        ref_y, ref_sr = self.load_audio_for_scoring(reference_sr_path)
        pitch_score = self._calculate_pitch_accuracy(user_f0, ref_f0)
        rhythm_score = self._calculate_rhythm_accuracy(user_y, user_sr, ref_y, ref_sr)
        vibrato_score = self._calculate_vibrato_quality(user_f0, ref_f0)
        final_score = (pitch_score * 0.5) + (rhythm_score * 0.3) + (vibrato_score * 0.2)
        return {
            "final_score": round(final_score, 2),
            "pitch_accuracy": round(pitch_score, 2),
            "rhythm_accuracy": round(rhythm_score, 2),
            "vibrato_quality": round(vibrato_score, 2),
            "user_pitch_contour": user_f0[~np.isnan(user_f0)].tolist(),
            "ref_pitch_contour": ref_f0[~np.isnan(ref_f0)].tolist(),
        }

    def generate_feedback(self, scores):
        feedback_messages = []
        if scores["pitch_accuracy"] < 50:
            feedback_messages.append("고음에서 음정이 자주 흔들려요. 호흡을 더 길게 유지해 보세요.")
        elif scores["pitch_accuracy"] < 70:
            feedback_messages.append("음정은 대체로 정확했지만, 몇몇 어려운 구간에서 흔들림이 있었어요.")
        else:
            feedback_messages.append("아주 정확한 음정! 훌륭하게 노래를 불렀어요.")
        if scores["rhythm_accuracy"] < 50:
            feedback_messages.append("박자가 자주 어긋났어요. 노래를 들으며 비트를 더 느껴보세요.")
        elif scores["rhythm_accuracy"] < 70:
            feedback_messages.append("박자는 전체적으로 좋았지만, 후렴에서 조금 빨라지거나 느려지는 경향이 있었어요.")
        else:
            feedback_messages.append("완벽한 박자감! 리듬을 아주 잘 탔어요.")
        if scores["vibrato_quality"] < 30:
            feedback_messages.append("바이브레이션이 거의 없어서 단조롭게 들려요. 긴 음에서 약간의 떨림을 넣어 보세요.")
        elif scores["vibrato_quality"] < 70:
            feedback_messages.append("바이브레이션이 있었지만, 좀 더 안정적으로 다듬을 수 있을 것 같아요.")
        else:
            feedback_messages.append("아름다운 바이브레이션! 노래에 깊이를 더했어요.")
        if scores["final_score"] > 80:
            feedback_messages.append("최고의 노래 실력이에요! 다음번에는 100점에 도전해보세요!")
        elif scores["final_score"] > 60:
            feedback_messages.append("아주 잘했어요! 조금만 더 연습하면 더 높은 점수를 받을 수 있을 거예요.")
        else:
            feedback_messages.append("괜찮은 시도였어요! 꾸준히 연습하면 분명 늘 거예요.")
        return feedback_messages

    def get_realtime_pitch_feedback(self, current_user_f0, target_ref_f0):
        if np.isnan(current_user_f0) or np.isnan(target_ref_f0) or target_ref_f0 == 0:
            return "No Pitch"
        cents_diff = 1200 * np.log2(current_user_f0 / target_ref_f0)
        if abs(cents_diff) < 25:
            return "Perfect"
        elif abs(cents_diff) < 75:
            return "Good"
        elif abs(cents_diff) < 150:
            return "Normal"
        else:
            return "Bad"
