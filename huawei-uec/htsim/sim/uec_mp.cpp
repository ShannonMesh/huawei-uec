
#include "uec_mp.h"

#include <iostream>


UecMpOblivious::UecMpOblivious(uint16_t no_of_paths,
                               bool debug)
    : UecMultipath(debug),
      _no_of_paths(no_of_paths),
      _current_ev_index(0)
      {

    _path_random = rand() % UINT16_MAX;  // random upper bits of EV
    _path_xor = rand() % _no_of_paths;

    if (_debug)
        cout << "Multipath"
            << " Oblivious"
            << " _no_of_paths " << _no_of_paths
            << " _path_random " << _path_random
            << " _path_xor " << _path_xor
            << endl;
}

void UecMpOblivious::processEv(uint16_t path_id, PathFeedback feedback) {
    return;
}

uint16_t UecMpOblivious::nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) {
    // _no_of_paths must be a power of 2
    uint16_t mask = _no_of_paths - 1;
    uint16_t entropy = (_current_ev_index ^ _path_xor) & mask;

    // set things for next time
    _current_ev_index++;
    if (_current_ev_index == _no_of_paths) {
        _current_ev_index = 0;
        _path_xor = rand() & mask;
    }

    entropy |= _path_random ^ (_path_random & mask);  // set upper bits
    return entropy;
}


UecMpBitmap::UecMpBitmap(uint16_t no_of_paths, bool debug)
    : UecMultipath(debug),
      _no_of_paths(no_of_paths),
      _current_ev_index(0),
      _ev_skip_bitmap(),
      _ev_skip_count(0)
      {

    _max_penalty = 15;

    _path_random = rand() % 0xffff;  // random upper bits of EV
    _path_xor = rand() % _no_of_paths;

    _ev_skip_bitmap.resize(_no_of_paths);
    for (uint32_t i = 0; i < _no_of_paths; i++) {
        _ev_skip_bitmap[i] = 0;
    }

    if (_debug)
        cout << "Multipath"
            << " Bitmap"
            << " _no_of_paths " << _no_of_paths
            << " _path_random " << _path_random
            << " _path_xor " << _path_xor
            << " _max_penalty " << (uint32_t)_max_penalty
            << endl;
}

void UecMpBitmap::processEv(uint16_t path_id, PathFeedback feedback) {
    // _no_of_paths must be a power of 2
    uint16_t mask = _no_of_paths - 1;
    path_id &= mask;  // only take the relevant bits for an index

    if (feedback != PathFeedback::PATH_GOOD && !_ev_skip_bitmap[path_id])
        _ev_skip_count++;

    uint8_t penalty = 0;

    if (feedback == PathFeedback::PATH_ECN)
        penalty = 1;
    else if (feedback == PathFeedback::PATH_NACK)
        penalty = 4;
    else if (feedback == PathFeedback::PATH_TIMEOUT)
        penalty = _max_penalty;

    _ev_skip_bitmap[path_id] += penalty;
    if (_ev_skip_bitmap[path_id] > _max_penalty) {
        _ev_skip_bitmap[path_id] = _max_penalty;
    }
}

uint16_t UecMpBitmap::nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) {
    // _no_of_paths must be a power of 2
    uint16_t mask = _no_of_paths - 1;
    uint16_t entropy = (_current_ev_index ^ _path_xor) & mask;
    bool flag = false;
    int counter = 0;
    while (_ev_skip_bitmap[entropy] > 0) {
        if (flag == false){
            _ev_skip_bitmap[entropy]--;
            if (!_ev_skip_bitmap[entropy]){
                assert(_ev_skip_count>0);
                _ev_skip_count--;
            }
        }

        flag = true;
        counter ++;
        if (counter > _no_of_paths){
            break;
        }
        _current_ev_index++;
        if (_current_ev_index == _no_of_paths) {
            _current_ev_index = 0;
            _path_xor = rand() & mask;
        }
        entropy = (_current_ev_index ^ _path_xor) & mask;
    }

    // set things for next time
    _current_ev_index++;
    if (_current_ev_index == _no_of_paths) {
        _current_ev_index = 0;
        _path_xor = rand() & mask;
    }

    entropy |= _path_random ^ (_path_random & mask);  // set upper bits
    return entropy;
}

UecMpReps::UecMpReps(uint16_t no_of_paths, bool debug, bool is_trimming_enabled)
    : UecMultipath(debug),
      _no_of_paths(no_of_paths),
      _crt_path(0),
      _is_trimming_enabled(is_trimming_enabled) {

    circular_buffer_reps = new CircularBufferREPS<uint16_t>(CircularBufferREPS<uint16_t>::repsBufferSize);

    if (_debug)
        cout << "Multipath"
            << " REPS"
            << " _no_of_paths " << _no_of_paths
            << endl;
}

void UecMpReps::processEv(uint16_t path_id, PathFeedback feedback) {

    if ((feedback == PATH_TIMEOUT) && !circular_buffer_reps->isFrozenMode() && circular_buffer_reps->explore_counter == 0) {
        if (_is_trimming_enabled) { // If we have trimming enabled
            circular_buffer_reps->setFrozenMode(true);
            circular_buffer_reps->can_exit_frozen_mode = EventList::getTheEventList().now() +  circular_buffer_reps->exit_freeze_after;
        } else {
            cout << timeAsUs(EventList::getTheEventList().now()) << "REPS currently requires trimming in this implementation." << endl;
            exit(EXIT_FAILURE); // If we reach this point, it means we are trying to enter freezing mode without trimming enabled.
        } // In this version of REPS, we do not enter freezing mode without trimming enabled. Check the REPS paper to implement it also without trimming.
    }

    if (circular_buffer_reps->isFrozenMode() && EventList::getTheEventList().now() > circular_buffer_reps->can_exit_frozen_mode) {
        circular_buffer_reps->setFrozenMode(false);
        circular_buffer_reps->resetBuffer();
        circular_buffer_reps->explore_counter = 16;
    }

    if ((feedback == PATH_GOOD) && !circular_buffer_reps->isFrozenMode()) {
        circular_buffer_reps->add(path_id);
    } else if (circular_buffer_reps->isFrozenMode() && (feedback == PATH_GOOD)) {
        circular_buffer_reps->add(path_id);
    }
}

uint16_t UecMpReps::nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) {
    if (circular_buffer_reps->explore_counter > 0) {
        circular_buffer_reps->explore_counter--;
        return rand() % _no_of_paths;
    }

    if (circular_buffer_reps->isFrozenMode()) {
        if (circular_buffer_reps->isEmpty()) {
            return rand() % _no_of_paths;
        } else {
            return circular_buffer_reps->remove_frozen();
        }
    } else {
        if (circular_buffer_reps->isEmpty() || circular_buffer_reps->getNumberFreshEntropies() == 0) {
            return _crt_path = rand() % _no_of_paths;
        } else {
            return circular_buffer_reps->remove_earliest_fresh();
        }
    }
}


UecMpRepsLegacy::UecMpRepsLegacy(uint16_t no_of_paths, bool debug)
    : UecMultipath(debug),
      _no_of_paths(no_of_paths),
      _crt_path(0) {

    if (_debug)
        cout << "Multipath"
            << " REPS"
            << " _no_of_paths " << _no_of_paths
            << endl;
}

void UecMpRepsLegacy::processEv(uint16_t path_id, PathFeedback feedback) {
    if (feedback == PATH_GOOD){
        _next_pathid.push_back(path_id);
        if (_debug){
            cout << timeAsUs(EventList::getTheEventList().now()) << " " << _debug_tag << " REPS Add " << path_id << " " << _next_pathid.size() << endl;
        }
    }
}

uint16_t UecMpRepsLegacy::nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) {
    if (seq_sent < min(cur_cwnd_in_pkts, (uint64_t)_no_of_paths)) {
        _crt_path++;
        if (_crt_path == _no_of_paths) {
            _crt_path = 0;
        }

        if (_debug) 
            cout << timeAsUs(EventList::getTheEventList().now()) << " " << _debug_tag << " REPS FirstWindow " << _crt_path << endl;

    } else {
        if (_next_pathid.empty()) {
            assert(_no_of_paths > 0);
		    _crt_path = random() % _no_of_paths;

            if (_debug) 
                cout << timeAsUs(EventList::getTheEventList().now()) << " " << _debug_tag << " REPS Steady " << _crt_path << endl;

        } else {
            _crt_path = _next_pathid.front();
            _next_pathid.pop_front();

            if (_debug) 
                cout << timeAsUs(EventList::getTheEventList().now()) << " " << _debug_tag << " REPS Recycle " << _crt_path << " " << _next_pathid.size() << endl;

        }
    }
    return _crt_path;
}

optional<uint16_t> UecMpRepsLegacy::nextEntropyRecycle() {
    if (_next_pathid.empty()) {
        return {};
    } else {
        _crt_path = _next_pathid.front();
        _next_pathid.pop_front();

        if (_debug) 
            cout << timeAsUs(EventList::getTheEventList().now()) << " " << _debug_tag << " MIXED Recycle " << _crt_path << " " << _next_pathid.size() << endl;
        return { _crt_path };
    }
}


UecMpMixed::UecMpMixed(uint16_t no_of_paths, bool debug)
    : UecMultipath(debug),
      _bitmap(UecMpBitmap(no_of_paths, debug)),
      _reps_legacy(UecMpRepsLegacy(no_of_paths, debug))
      {
}

void UecMpMixed::set_debug_tag(string debug_tag) {
    _bitmap.set_debug_tag(debug_tag);
    _reps_legacy.set_debug_tag(debug_tag);
}

void UecMpMixed::processEv(uint16_t path_id, PathFeedback feedback) {
    _bitmap.processEv(path_id, feedback);
    _reps_legacy.processEv(path_id, feedback);
}

uint16_t UecMpMixed::nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) {
    auto reps_val = _reps_legacy.nextEntropyRecycle();
    if (reps_val.has_value()) {
        return reps_val.value();
    } else {
        return _bitmap.nextEntropy(seq_sent, cur_cwnd_in_pkts);
    }
}

UecMpHashx::UecMpHashx(uint16_t no_of_paths, bool debug, uint32_t src, uint32_t dst,
                       uint64_t ecn_low, uint64_t ecn_high, uint32_t max_weight)
    : UecMultipath(debug),
      _no_of_paths(no_of_paths),
      _path_weights(),
      _src(src),
      _dst(dst),
      _ecn_low(ecn_low),
      _ecn_high(ecn_high),
      _max_weight(max_weight)
      {
    // 使用 src 和 dst 计算初始路径（使用大质数增加哈希分散性）
    // const uint32_t HASH_PRIME = 2654435761u;  // 大质数
    // _current_path =  _dst % _no_of_paths;
    _current_path = random() % _no_of_paths;

    _path_weights.resize(_no_of_paths);
    for (uint32_t i = 0; i < _no_of_paths; i++) {
        _path_weights[i] = _max_weight;
    }

    if (_debug)
        cout << "Multipath"
             << " Hashx"
             << " _no_of_paths " << _no_of_paths
             << " src " << _src
             << " dst " << _dst
             << " initial_path " << _current_path
             << " ecn_low " << _ecn_low
             << " ecn_high " << _ecn_high
             << " max_weight " << _max_weight
             << endl;
}

void UecMpHashx::processEv(uint16_t path_id, PathFeedback feedback) {
    if (_debug) {
        cout << timeAsUs(EventList::getTheEventList().now()) << " " << _debug_tag
             << " Hashx processEv path_id " << path_id
             << " feedback " << feedback << endl;
    }
}

void UecMpHashx::processEv(uint16_t path_id, uint64_t queue_size_low, uint64_t queue_size_high, int ecn_tag) {
    if (ecn_tag == 3) {
        // ECN tag = 3, do nothing
        if (_debug) {
            cout << timeAsUs(EventList::getTheEventList().now()) << " " << _debug_tag
                 << " Hashx processEvECN path_id " << path_id
                 << " ecn_tag=3, no action" << endl;
        }
        return;
    }

    if (ecn_tag == 1) {
        // ECN tag = 1, calculate weight based on queue size
        if (path_id < _no_of_paths) {
            int new_weight = 0;
            if (_ecn_high > _ecn_low) {
                // Calculate: _max_weight * (1 - (queue_low - ecn_low) / (ecn_high - ecn_low))
                if (queue_size_low <= _ecn_low) {
                    new_weight = _max_weight;  // Queue below low threshold, full weight
                } else if (queue_size_low >= _ecn_high) {
                    new_weight = 0;  // Queue above high threshold, zero weight
                } else {
                    // Linear interpolation: weight = _max_weight * (1 - (queue_low - ecn_low) / (ecn_high - ecn_low))
                    uint64_t numerator = _max_weight * (_ecn_high - queue_size_low);
                    uint64_t denominator = _ecn_high - _ecn_low;
                    new_weight = (int)(numerator / denominator);
                    if (new_weight < 0) new_weight = 0;
                    if (new_weight > (int)_max_weight) new_weight = _max_weight;
                }
            } else {
                // Invalid thresholds, use default
                new_weight = _max_weight;
            }
            _path_weights[path_id] = new_weight;
            if (_debug) {
                cout << timeAsUs(EventList::getTheEventList().now()) << " " << _debug_tag
                     << " Hashx processEvECN path_id " << path_id
                     << " ecn_tag=1, queue_low=" << queue_size_low
                     << " ecn_low=" << _ecn_low << " ecn_high=" << _ecn_high
                     << " new_weight=" << new_weight << endl;
            }
        }
        return;
    }

    // Other ecn_tag values, just log for now
    if (_debug) {
        cout << timeAsUs(EventList::getTheEventList().now()) << " " << _debug_tag
             << " Hashx processEvECN path_id " << path_id
             << " queue_low " << queue_size_low
             << " queue_high " << queue_size_high
             << " ecn_tag " << ecn_tag << endl;
    }
}

uint16_t UecMpHashx::nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) {
    uint16_t selected_path = _current_path;

    // Check if current path weight is less than _max_weight, increment and skip
    while (_path_weights[selected_path] < (int)_max_weight) {
        if (_debug) {
            cout << timeAsUs(EventList::getTheEventList().now()) << " " << _debug_tag
                 << " Hashx nextEntropy path " << selected_path
                 << " weight=" << _path_weights[selected_path]
                 << " incrementing and skipping" << endl;
        }
        _path_weights[selected_path]++;  // increment weight by 1
        _current_path = (_current_path + 1) % _no_of_paths;
        selected_path = _current_path;
    }

    // Move to next path for next time
    _current_path = (_current_path + 1) % _no_of_paths;

    if (_debug) {
        cout << timeAsUs(EventList::getTheEventList().now()) << " " << _debug_tag
             << " Hashx nextEntropy selected_path " << selected_path
             << " weight " << _path_weights[selected_path]
             << " next_path " << _current_path << endl;
    }

    return selected_path;
}

UecMpRandom::UecMpRandom(uint16_t no_of_paths, bool debug)
    : UecMultipath(debug),
      _no_of_paths(no_of_paths) {

    if (_debug)
        cout << "Multipath"
             << " Random"
             << " _no_of_paths " << _no_of_paths
             << endl;
}

void UecMpRandom::processEv(uint16_t path_id, PathFeedback feedback) {
    return;
}

uint16_t UecMpRandom::nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) {
    uint16_t selected_path = random() % 65536;

    if (_debug) {
        cout << timeAsUs(EventList::getTheEventList().now()) << " " << _debug_tag
             << " Random nextEntropy selected_path " << selected_path << endl;
    }

    return selected_path;
}