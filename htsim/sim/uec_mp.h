// -*- c-basic-offset: 4; indent-tabs-mode: nil -*-
#ifndef UEC_MP_H
#define UEC_MP_H

#include <list>
#include <optional>
#include "eventlist.h"
#include "buffer_reps.h"
#include <map>
#include <unordered_map>
#include <limits>


class UecMultipath {
public:
    enum PathFeedback {PATH_GOOD, PATH_ECN, PATH_NACK, PATH_TIMEOUT};
    enum EvDefaults {UNKNOWN_EV};
    UecMultipath(bool debug): _debug(debug), _debug_tag("") {};
    virtual ~UecMultipath() {};
    virtual void set_debug_tag(string debug_tag) { _debug_tag = debug_tag; };
    /**
     * @param uint16_t path_id The path ID/entropy value as received by ACK/NACK
     * @param PathFeedback path_id The ACK/NACK response
     */
    virtual void processEv(uint16_t path_id, PathFeedback feedback) = 0;
    /**
     * @param uint16_t path_id The path ID from ECN notification
     * @param queue_size_low Queue size at low priority
     * @param queue_size_high Queue size at high priority
     * @param ecn_tag ECN tag value
     */
    virtual void processEv(uint16_t path_id, uint64_t queue_size_low, uint64_t queue_size_high, int ecn_tag) {};

    virtual void processEv(uint16_t path_id, uint32_t switch_id, uint32_t port_id) {};

    virtual bool lastActionWasLB() const { return false; }

    virtual void processEv(uint16_t path_id, PathFeedback feedback, simtime_picosec rtt) {}
    /**
     * @param uint64_t seq_sent The sequence number to be sent
     * @param uint64_t cur_cwnd_in_pkts The current congestion window in packets.
     */
    virtual uint16_t nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) = 0;
protected:
    bool _debug;
    string _debug_tag;
};

class UecMpOblivious : public UecMultipath {
public:
    UecMpOblivious(uint16_t no_of_paths, bool debug);
    void processEv(uint16_t path_id, PathFeedback feedback) override;
    uint16_t nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) override;
private:
    uint16_t _no_of_paths;       // must be a power of 2
    uint16_t _path_random;       // random upper bits of EV, set at startup and never changed
    uint16_t _path_xor;          // random value set each time we wrap the entropy values - XOR with
                                 // _current_ev_index
    uint16_t _current_ev_index;  // count through _no_of_paths and then wrap.  XOR with _path_xor to
};

class UecMpBitmap : public UecMultipath {
public:
    UecMpBitmap(uint16_t no_of_paths, bool debug);
    void processEv(uint16_t path_id, PathFeedback feedback) override;
    uint16_t nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) override;
private:
    uint16_t _no_of_paths;       // must be a power of 2
    uint16_t _path_random;       // random upper bits of EV, set at startup and never changed
    uint16_t _path_xor;          // random value set each time we wrap the entropy values - XOR with
                                 // _current_ev_index
    uint16_t _current_ev_index;  // count through _no_of_paths and then wrap.  XOR with _path_xor to
    vector<uint8_t> _ev_skip_bitmap;  // paths scores for load balancing

    uint16_t _ev_skip_count;
    uint8_t _max_penalty;             // max value we allow in _path_penalties (typically 1 or 2).
};

class UecMpRepsLegacy : public UecMultipath {
public:
    UecMpRepsLegacy(uint16_t no_of_paths, bool debug);
    void processEv(uint16_t path_id, PathFeedback feedback) override;
    uint16_t nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) override;
    optional<uint16_t> nextEntropyRecycle();
private:
    uint16_t _no_of_paths;
    uint16_t _crt_path;
    list<uint16_t> _next_pathid;
};


class UecMpReps : public UecMultipath {
public:
    UecMpReps(uint16_t no_of_paths, bool debug, bool is_trimming_enabled);
    void processEv(uint16_t path_id, PathFeedback feedback) override;
    uint16_t nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) override;
private:
    uint16_t _no_of_paths;
    CircularBufferREPS<uint16_t> *circular_buffer_reps;
    uint16_t _crt_path;
    list<uint16_t> _next_pathid;
    bool _is_trimming_enabled = true;  // whether to trim the circular buffer
};

class UecMpMixed : public UecMultipath {
public:
    UecMpMixed(uint16_t no_of_paths, bool debug);
    void processEv(uint16_t path_id, PathFeedback feedback) override;
    uint16_t nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) override;
    void set_debug_tag(string debug_tag) override;
private:
    UecMpBitmap _bitmap;
    UecMpRepsLegacy _reps_legacy;
};

class UecMpHashx : public UecMultipath {
public:
    UecMpHashx(uint16_t no_of_paths, bool debug, uint32_t src = 0, uint32_t dst = 0,
               uint64_t ecn_low = 0, uint64_t ecn_high = 0, uint32_t max_weight = 8);
    void processEv(uint16_t path_id, PathFeedback feedback) override;
    void processEv(uint16_t path_id, uint64_t queue_size_low, uint64_t queue_size_high, int ecn_tag) override;
    void processEv(uint16_t path_id, uint32_t switch_id, uint32_t port_id) override;  
    void processEv(uint16_t path_id, PathFeedback feedback, simtime_picosec rtt) override;
    uint16_t nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) override;
    void addMultipathEntry(uint32_t switch_id, uint32_t port_id, const std::vector<uint32_t>& alternatives);
    void setPathCooldown(simtime_picosec cooldown) { _path_cooldown = cooldown; }
    static std::map<std::pair<uint32_t,uint32_t>, std::vector<uint32_t>> _multipath_table;
    static bool _table_built;   
private:
    uint16_t _no_of_paths;       // must be a power of 2
    uint16_t _current_path;      // current path index for round-robin
    vector<int> _path_weights;   // path weights for load balancing
    uint32_t _src;               // source host ID
    uint32_t _dst;               // destination host ID
    uint64_t _ecn_low;           // ECN low threshold (in bytes)
    uint64_t _ecn_high;          // ECN high threshold (in bytes)
    uint32_t _max_weight;        // maximum weight value (default: 8)


    bool     _last_action_was_lb = false;
    uint32_t _cached_entropy     = 0;
    simtime_picosec _path_cooldown = 0;

    struct PathStat {
    simtime_picosec avg_rtt      = 0;
    uint64_t        ecn_count    = 0;
    uint64_t        total_count  = 0;
    simtime_picosec last_bad_time = 0;
    uint64_t        switch_count  = 0; 
    };

    static std::unordered_map<uint32_t, PathStat> _path_stats;  

    void handleLB(uint16_t path_id, const std::vector<uint32_t>& alternatives);
    uint32_t selectBestAlternative(const std::vector<uint32_t>& candidates, uint32_t bad_path);
    bool lastActionWasLB() const override { return _last_action_was_lb; }

    uint32_t _next_entropy = 0;
    bool allEntropiesTried() const { return _next_entropy >= _no_of_paths; }
};

class UecMpRandom : public UecMultipath {
public:
    UecMpRandom(uint16_t no_of_paths, bool debug);
    void processEv(uint16_t path_id, PathFeedback feedback) override;
    uint16_t nextEntropy(uint64_t seq_sent, uint64_t cur_cwnd_in_pkts) override;
private:
    uint16_t _no_of_paths;
};


#endif  // UEC_MP_H
