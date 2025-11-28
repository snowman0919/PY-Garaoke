import numpy as np
import librosa
import librosa.display
import os
import random

class KaraokeScorer:
    def __init__(self, sr=22050, hop_length=512):
        self.sr = sr
        self.hop_length = hop_length

    def _extract_pitch(self, audio_path):
        # Optimize: Load at a lower sample rate (8000 Hz) for faster pitch detection
        # This significantly reduces the data size and processing time for pyin
        analysis_sr = 8000
        y, sr = librosa.load(audio_path, sr=analysis_sr)
        
        # Use a slightly larger hop_length relative to the lower SR to keep frames reasonable
        # 22050 / 512 ~= 43 Hz resolution. 8000 / 192 ~= 41 Hz resolution.
        hop_length_low = int(self.hop_length * (analysis_sr / self.sr))
        if hop_length_low < 64: hop_length_low = 64

        # Run pyin on the downsampled audio
        f0, _, _ = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=sr, hop_length=hop_length_low)
        
        # Interpolate f0 back to the original sample rate/hop_length timeline if necessary for exact alignment
        # But since we compare user vs ref, as long as both are processed this way, it's fine.
        # However, the scoring logic compares frame-by-frame. We must ensure user and ref have same time grid.
        # The scorer uses self.hop_length and self.sr. 
        # If we return a different time grid, scoring will fail or misalign.
        
        # To fix alignment without complex interpolation: 
        # 1. Calculate times for the low-sr frames.
        # 2. Resample f0 to the expected original timeline (sr=22050, hop=512).
        
        times_low = librosa.times_like(f0, sr=sr, hop_length=hop_length_low)
        times_orig = np.arange(0, len(y)/sr, self.hop_length/self.sr)
        
        # Interpolate f0 to original timeline
        f0_interp = np.interp(times_orig, times_low, f0, left=np.nan, right=np.nan)
        
        # Also we need y at original SR for rhythm calculation? 
        # The _calculate_rhythm_accuracy uses onset detection.
        # We should probably just reload y at original SR if needed, or accept the low SR y.
        # _calculate_rhythm_accuracy takes y and sr as args. So we can pass the low SR versions!
        # But wait, _calculate_pitch_accuracy compares user_f0 and ref_f0.
        # If we extract both with this method, they will align to times_orig (calculated above).
        # So we are good!
        
        # We return the interpolated f0 matching the global grid, but the low-sr audio.
        # This is a compromise. Rhythm detection on 8kHz is "okay" but not perfect.
        # For better quality, we might reload y at full SR, but that's slow I/O.
        # Let's return the low SR y and sr. The rhythm function handles its own onset detection.
        
        return f0_interp, y, sr

    def _quantize_pitch_to_notes(self, f0):
        # Convert frequency to MIDI notes, then to the nearest musical note
        midi_notes = librosa.hz_to_midi(f0)
        # Filter out NaN values (unvoiced)
        valid_midi = midi_notes[~np.isnan(midi_notes)]
        quantized_midi = np.round(valid_midi)
        return quantized_midi

    def _calculate_pitch_accuracy(self, user_f0, ref_f0, tolerance_cents=50):
        # Align lengths (simple approach: trim to shorter length or interpolate)
        min_len = min(len(user_f0), len(ref_f0))
        user_f0_trimmed = user_f0[:min_len]
        ref_f0_trimmed = ref_f0[:min_len]

        # Ignore unvoiced segments (where f0 is NaN or very low) in reference
        valid_indices = ~np.isnan(ref_f0_trimmed) & (ref_f0_trimmed > 0)
        
        if not np.any(valid_indices):
            return 0.0 # No valid reference pitch to compare against

        user_f0_valid = user_f0_trimmed[valid_indices]
        ref_f0_valid = ref_f0_trimmed[valid_indices]

        if len(user_f0_valid) == 0:
            return 0.0 # No user pitch in valid reference segments

        # Convert to cents difference
        cents_diff = 1200 * np.log2(user_f0_valid / ref_f0_valid)
        
        # Calculate accuracy based on tolerance
        accurate_frames = np.abs(cents_diff) < tolerance_cents
        score = np.sum(accurate_frames) / len(accurate_frames)
        return score * 100 # Return as percentage

    def _calculate_rhythm_accuracy(self, user_y, user_sr, ref_y, ref_sr, tolerance_frames=3):
        # Onset detection for both signals
        user_onsets = librosa.onset.onset_detect(y=user_y, sr=user_sr, hop_length=self.hop_length)
        ref_onsets = librosa.onset.onset_detect(y=ref_y, sr=ref_sr, hop_length=self.hop_length)

        # Use frame indices directly
        user_onset_frames = user_onsets
        ref_onset_frames = ref_onsets

        if len(ref_onset_frames) == 0:
            return 100.0 # No reference onsets, perfect rhythm (or no rhythm to match)

        matched_onsets = 0
        used_user_onsets = np.zeros_like(user_onset_frames, dtype=bool)

        for ref_frame in ref_onset_frames:
            # Find the closest user onset that hasn't been used yet
            distances = np.abs(user_onset_frames - ref_frame)
            if len(distances) == 0:
                continue
            closest_user_idx = np.argmin(distances)

            if not used_user_onsets[closest_user_idx] and distances[closest_user_idx] < tolerance_frames:
                matched_onsets += 1
                used_user_onsets[closest_user_idx] = True
        
        # Score is proportion of reference onsets that were matched
        score = (matched_onsets / len(ref_onset_frames)) if len(ref_onset_frames) > 0 else 0
        return score * 100

    def _calculate_vibrato_quality(self, user_f0, ref_f0, min_vibrato_hz=2, max_vibrato_hz=7, min_duration_sec=0.2):
        # A very simplified approach to vibrato detection for karaoke scoring
        # Identify sustained notes in the reference where vibrato *might* be expected.
        # Then check if user's pitch in those segments shows some oscillation.

        # Ignore unvoiced segments
        ref_f0_clean = ref_f0[~np.isnan(ref_f0) & (ref_f0 > 0)]
        user_f0_clean = user_f0[~np.isnan(user_f0) & (user_f0 > 0)]

        min_frames = int(self.sr * min_duration_sec / self.hop_length)
        if len(ref_f0_clean) < min_frames or len(user_f0_clean) < min_frames:
            return 0.0 # Not enough audio to analyze vibrato

        # Basic vibrato proxy: standard deviation of pitch within sustained segments
        # This is very crude and would ideally involve more complex signal processing
        
        # Find segments of relatively stable pitch in reference (potential for vibrato)
        # (This is a placeholder, a real implementation would be more robust)
        ref_f0_diff = np.diff(ref_f0_clean)
        stable_segments = np.where(np.abs(ref_f0_diff) < 5)[0] # Threshold for "stable" Hz change

        if len(stable_segments) == 0:
            return 50.0 # Cannot detect stable segments in reference, neutral score

        # Take a random stable segment from reference for analysis (simplification)
        # In a real app, iterate through all sustained notes
        start_idx = stable_segments[0]
        end_idx = start_idx + int(self.sr * min_duration_sec / self.hop_length)
        if end_idx >= len(ref_f0_clean):
            return 50.0 # Segment too short

        ref_segment = ref_f0_clean[start_idx:end_idx]
        user_segment = user_f0_clean[start_idx:end_idx] # Assume rough alignment

        if len(user_segment) < len(ref_segment):
            return 50.0 # User segment too short

        # Check for pitch variation in user's segment
        user_segment_std = np.std(user_segment)
        
        # Arbitrary scoring based on std dev
        if user_segment_std > min_vibrato_hz and user_segment_std < max_vibrato_hz:
            return 100.0 # Good vibrato range
        elif user_segment_std >= max_vibrato_hz:
            return 30.0 # Too wide/unstable
        elif user_segment_std <= min_vibrato_hz and user_segment_std > 0.1:
            return 70.0 # Some vibrato, but maybe not strong enough
        else:
            return 0.0 # No vibrato detected or very flat

    def score_performance(self, user_take_path, reference_sr_path):
        user_f0, user_y, user_sr = self._extract_pitch(user_take_path)
        ref_f0, ref_y, ref_sr = self._extract_pitch(reference_sr_path)

        # Pitch Accuracy
        pitch_score = self._calculate_pitch_accuracy(user_f0, ref_f0)

        # Rhythm Accuracy
        rhythm_score = self._calculate_rhythm_accuracy(user_y, user_sr, ref_y, ref_sr)

        # Vibrato Quality
        vibrato_score = self._calculate_vibrato_quality(user_f0, ref_f0)

        # Combine into final score
        final_score = (pitch_score * 0.5) + (rhythm_score * 0.3) + (vibrato_score * 0.2)
        
        return {
            "final_score": round(final_score, 2),
            "pitch_accuracy": round(pitch_score, 2),
            "rhythm_accuracy": round(rhythm_score, 2),
            "vibrato_quality": round(vibrato_score, 2),
            "user_pitch_contour": user_f0[~np.isnan(user_f0)].tolist(), # Return clean contours for visualization
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
        # This function is intended for real-time, lightweight feedback.
        # It assumes current_user_f0 and target_ref_f0 are single frequency values
        if np.isnan(current_user_f0) or np.isnan(target_ref_f0) or target_ref_f0 == 0:
            return "No Pitch"

        cents_diff = 1200 * np.log2(current_user_f0 / target_ref_f0)

        if abs(cents_diff) < 25: # +/- a quarter tone
            return "Perfect"
        elif abs(cents_diff) < 75: # +/- three quarters of a tone
            return "Good"
        elif abs(cents_diff) < 150: # +/- one and a half tones
            return "Normal"
        else:
            return "Bad"
