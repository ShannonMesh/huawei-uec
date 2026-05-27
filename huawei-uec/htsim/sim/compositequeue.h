// -*- c-basic-offset: 4; indent-tabs-mode: nil -*-        
#ifndef COMPOSITE_QUEUE_H
#define COMPOSITE_QUEUE_H

/*
 * A composite queue that transforms packets into headers when there is no space and services headers with priority. 
 */

#define QUEUE_INVALID 0
#define QUEUE_LOW 1
#define QUEUE_HIGH 2

// ECN decision return values
#define ECN_NO_MARK 0       // 不打标记
#define ECN_MARK 1          // 打ECN标记
#define ECN_LOW_WATERMARK 2 // 低于low水线，特殊处理


#include <list>
#include "queue.h"
#include "config.h"
#include "eventlist.h"
#include "network.h"
#include "loggertypes.h"

class CompositeQueue;  // Forward declaration

class QueueStatsTimer : public EventSource {
public:
    QueueStatsTimer(CompositeQueue* queue, EventList& eventlist);
    virtual void doNextEvent();
    bool isTraffic() { return false; };  // Not a traffic event, won't block simulation end

private:
    CompositeQueue* _queue;
    simtime_picosec _interval;
    simtime_picosec _next_stats_time;

    // Previous queue depth for calculating change rate
    mem_b _last_q_low;
};

class CompositeQueue : public Queue {
    friend class QueueStatsTimer;  // Allow QueueStatsTimer to access private members
 public:
    CompositeQueue(linkspeed_bps bitrate, mem_b maxsize,
                   EventList &eventlist, QueueLogger* logger,
                   uint16_t trim_size, bool disable_trim=false);
    virtual ~CompositeQueue();
    virtual void receivePacket(Packet& pkt);
    virtual void doNextEvent();
    // should really be private, but loggers want to see
    mem_b _queuesize_low,_queuesize_high;
    int num_headers() const { return _num_headers;}
    int num_packets() const { return _num_packets;}
    int num_stripped() const { return _num_stripped;}
    int num_bounced() const { return _num_bounced;}
    int num_acks() const { return _num_acks;}
    int num_nacks() const { return _num_nacks;}
    int num_pulls() const { return _num_pulls;}
    mem_b queuesize_high_watermark() const { return _queuesize_high_watermark;}
    virtual mem_b queuesize() const;
    virtual void setName(const string& name) {
        Logged::setName(name); 
        _nodename += name;
    }

    void setRTS(bool return_to_sender){ _return_to_sender = return_to_sender;}

    virtual const string& nodename() { return _nodename; }
    void set_ecn_threshold(mem_b ecn_thresh) {
        _ecn_minthresh = ecn_thresh;
        _ecn_maxthresh = ecn_thresh;
    }
    void set_ecn_thresholds(mem_b min_thresh, mem_b max_thresh) {
        _ecn_minthresh = min_thresh;
        _ecn_maxthresh = max_thresh;
        if (_queue_id == 2)
            cout << "queue_id " << _queue_id << " ecn_low " << _ecn_minthresh << " ecn_high " << _ecn_maxthresh << endl;
    }

    void set_ecn_tag(int ecn_tag) { _ecn_tag = ecn_tag; }

    // Getters and setters for w, we, and dq_dt (used by QueueStatsTimer)
    double getW() const { return _w; }
    double getWe() const { return _we; }
    double getDqDt() const { return _dq_dt; }
    void setW(double w) { _w = w; }
    void setWe(double we) { _we = we; }
    void setDqDt(double dq_dt) { _dq_dt = dq_dt; }

    // Static network RTT - shared across all queues
    static void setNetworkRtt(simtime_picosec rtt) { _network_rtt = rtt; }
    static simtime_picosec getNetworkRtt() { return _network_rtt; }

    // ECN notify echo back control
    static void setEnableEcnNotify(bool enable) { _enable_ecn_notify = enable; }
    static bool getEnableEcnNotify() { return _enable_ecn_notify; }

    // ECN marking timing control (enqueue vs dequeue)
    static void setEcnMarkOnEnqueue(bool on_enqueue) { _ecn_mark_on_enqueue = on_enqueue; }
    static bool getEcnMarkOnEnqueue() { return _ecn_mark_on_enqueue; }

    // NSCC fastcn mode control
    static void setNsccFastcn(bool enable) { _nscc_fastcn = enable; }
    static bool getNsccFastcn() { return _nscc_fastcn; }

    int _num_packets;
    int _num_headers; // only includes data packets stripped to headers, not acks or nacks
    int _num_acks;
    int _num_nacks;
    int _num_pulls;
    int _num_stripped; // count of packets we stripped
    int _num_bounced;  // count of packets we bounced
    mem_b _queuesize_high_watermark; // max occupancy of high priority queue

 protected:
    // Mechanism
    void beginService(); // start serving the item at the head of the queue
    void completeService(); // wrap up serving the item at the head of the queue
    int decide_ECN();
    void mark_ECN(Packet& pkt, bool on_enqueue); // 处理 ECN 标记（根据时机参数决定行为）

    bool _disable_trim;

    int _serv;
    int _ratio_high, _ratio_low, _crt;
    // below minthresh, 0% marking, between minthresh and maxthresh
    // increasing random mark propbability, abve maxthresh, 100%
    // marking.
    mem_b _ecn_minthresh; 
    mem_b _ecn_maxthresh;
    int _ecn_tag;

    uint16_t _trim_size;

    bool _return_to_sender;

    int _queue_id;
    CircularBuffer<Packet*> _enqueued_low;
    CircularBuffer<Packet*> _enqueued_high;

    // Statistics variables (updated by QueueStatsTimer)
    double _w;
    double _we;
    double _dq_dt;

    // Pointer to the stats timer (owned by this queue)
    QueueStatsTimer* _stats_timer;

    // Static network RTT - shared across all queues
    static simtime_picosec _network_rtt;

    // Static ECN notify echo back control - shared across all queues
    static bool _enable_ecn_notify;

    // Static ECN marking timing control - shared across all queues
    static bool _ecn_mark_on_enqueue;

    // Static NSCC fastcn mode control - shared across all queues
    static bool _nscc_fastcn;
};

#endif
