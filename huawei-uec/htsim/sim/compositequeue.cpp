// -*- c-basic-offset: 4; indent-tabs-mode: nil -*-        
#include "compositequeue.h"
#include <math.h>
#include <iostream>
#include <sstream>
#include "ecn.h"
#include "uecpacket.h"

static int global_queue_id=0;
#define DEBUG_QUEUE_ID -1 // set to queue ID to enable debugging

// Static network RTT - shared across all queues
simtime_picosec CompositeQueue::_network_rtt = 0;

// Static ECN notify echo back control - default disabled
bool CompositeQueue::_enable_ecn_notify = false;

// Static ECN marking timing control - default dequeue (false)
bool CompositeQueue::_ecn_mark_on_enqueue = false;

// Static NSCC fastcn mode control - default disabled
bool CompositeQueue::_nscc_fastcn = false;

CompositeQueue::CompositeQueue(linkspeed_bps bitrate, mem_b maxsize, EventList& eventlist, 
                               QueueLogger* logger, uint16_t trim_size, bool disable_trim)
    : Queue(bitrate, maxsize, eventlist, logger)
{
    _disable_trim = disable_trim;
    _trim_size = trim_size;
    _ratio_high = 100000;
    _ratio_low = 1;
    _crt = 0;
    _num_headers = 0;
    _num_packets = 0;
    _num_acks = 0;
    _num_nacks = 0;
    _num_pulls = 0;
    _num_drops = 0;
    _num_stripped = 0;
    _num_bounced = 0;
    _ecn_minthresh = maxsize*2; // don't set ECN by default
    _ecn_maxthresh = maxsize*2; // don't set ECN by default
    _ecn_tag = ECN_CE;

    _return_to_sender = false;

    _queuesize_high = _queuesize_low = 0;
    _queuesize_high_watermark = 0;
    _serv = QUEUE_INVALID;

    // Initialize statistics variables
    _w = 0.0;
    _we = 0.0;
    _dq_dt = 0.0;

    // Create the stats timer
    _stats_timer = new QueueStatsTimer(this, eventlist);

    stringstream ss;
    ss << "compqueue(" << bitrate/1000000 << "Mb/s," << maxsize << "bytes)";
    _nodename = ss.str();
    _queue_id = global_queue_id++;
    if (_queue_id == DEBUG_QUEUE_ID)
        cout << "queueid " << _queue_id << " bitrate " << bitrate/1000000 << "Mb/s," << endl;
}

CompositeQueue::~CompositeQueue()
{
    // Delete the stats timer
    delete _stats_timer;
}

void CompositeQueue::beginService(){
    if (!_enqueued_high.empty()&&!_enqueued_low.empty()){
        _crt++;

        if (_crt >= (_ratio_high+_ratio_low))
            _crt = 0;

        if (_crt< _ratio_high) {
            _serv = QUEUE_HIGH;
            eventlist().sourceIsPendingRel(*this, drainTime(_enqueued_high.back()));
        } else {
            assert(_crt < _ratio_high+_ratio_low);
            _serv = QUEUE_LOW;
            eventlist().sourceIsPendingRel(*this, drainTime(_enqueued_low.back()));      
        }
        return;
    }

    if (!_enqueued_high.empty()) {
        _serv = QUEUE_HIGH;
        eventlist().sourceIsPendingRel(*this, drainTime(_enqueued_high.back()));
    } else if (!_enqueued_low.empty()) {
        _serv = QUEUE_LOW;
        eventlist().sourceIsPendingRel(*this, drainTime(_enqueued_low.back()));
    } else {
        assert(0);
        _serv = QUEUE_INVALID;
    }
}

int CompositeQueue::decide_ECN() {
    //ECN mark on deque
    if (_queuesize_low > _ecn_maxthresh) {
        return ECN_MARK;
    } else if (_queuesize_low > _ecn_minthresh) {
        uint64_t p = (0x7FFFFFFF * (_queuesize_low - _ecn_minthresh))/(_ecn_maxthresh - _ecn_minthresh);
        if ((uint64_t)random() < p) {
            return ECN_MARK;
        }
    } else if (_nscc_fastcn && _queuesize_low > 0) {
        // NSCC fastcn 模式：队列深度在 0 和 _ecn_minthresh 之间
        // 概率标记：越接近 0，标记概率越高
        uint64_t p = (0x7FFFFFFF * (_ecn_minthresh - _queuesize_low)) / _ecn_minthresh;
        // 限制最大概率为 25%
        p = p;
        if ((uint64_t)random() < p) {
            return ECN_LOW_WATERMARK;
        }
        // random();
    }
    // random();
    return ECN_NO_MARK;
}

void CompositeQueue::completeService(){
    Packet* pkt;
    if (_serv==QUEUE_LOW){
        assert(!_enqueued_low.empty());
        pkt = _enqueued_low.pop();
        _queuesize_low -= pkt->size();

        // 处理 ECN 标记（根据配置在入队或出队时）
        mark_ECN(*pkt, false);  // false 表示出队时调用
        if (_queue_id == DEBUG_QUEUE_ID) {
            cout << timeAsUs(eventlist().now()) <<" name " <<_nodename <<" _queuesize_low " 
                << _queuesize_low*8/((_bitrate/1000000.0)) <<" _queueid " << _queue_id << " switch " << _switch->getID() 
                << " _queuesize_high " << _queuesize_high*8/((_bitrate/1000000.0))
                << endl;    

        }
        if (_logger) _logger->logQueue(*this, QueueLogger::PKT_SERVICE, *pkt);
        _num_packets++;
    } else if (_serv==QUEUE_HIGH) {
        assert(!_enqueued_high.empty());
        pkt = _enqueued_high.pop();
        if (_queuesize_high > _queuesize_high_watermark) {
            _queuesize_high_watermark = _queuesize_high;
        }
        _queuesize_high -= pkt->size();
        if (_logger) _logger->logQueue(*this, QueueLogger::PKT_SERVICE, *pkt);
        if (pkt->type() == NDPACK)
            _num_acks++;
        else if (pkt->type() == NDPNACK)
            _num_nacks++;
        else if (pkt->type() == NDPPULL)
            _num_pulls++;
        else {
            //cout << "Hdr: type=" << pkt->type() << endl;
            _num_headers++;
            //ECN mark on deque of a header, if low priority queue is still over threshold
//            if (decide_ECN()) {
//                pkt->set_flags(pkt->flags() | ECN_CE);
//            }
        }
    } else {
        assert(0);
    }
    
    // ========== 在网时延统计 ==========
    // 只统计低优先级队列的数据包（高优先级队列是 ACK/NACK/Header 等控制包）
    // 检查是否是 dtor 交换机的发送队列 (LS->DST，即 ToR 到 Server 的下行队列)
    // 队列名称格式为 "LS{X}->DST{Y}(Z)"
    if (_serv == QUEUE_LOW && 
        _nodename.find("LS") != string::npos && 
        _nodename.find("->DST") != string::npos) {
        // 这是 dtor 交换机的发送队列的低优先级数据包，记录数据包离开 dtor 的时间
        pkt->set_dtor_dequeue_time(eventlist().now());
        
        // 计算并输出在网时延
        simtime_picosec network_delay = pkt->get_network_delay();
        if (network_delay > 0) {
            // 可以选择输出到文件或存储到统计结构中
            // 这里先输出到控制台，你可以根据需要修改
            cout << "[NetworkDelay] pkt_id=" << pkt->id() 
                 << " flow_id=" << pkt->flow_id()
                 << " delay_us=" << timeAsUs(network_delay) 
                 << " stor_time=" << timeAsUs(pkt->get_stor_enqueue_time())
                 << " dtor_time=" << timeAsUs(pkt->get_dtor_dequeue_time())
                 << endl;
        }
    }
    // ==================================
    
    pkt->flow().logTraffic(*pkt,*this,TrafficLogger::PKT_DEPART);
    pkt->sendOn();

    //_virtual_time += drainTime(pkt);
  
    _serv = QUEUE_INVALID;
  
    if (!_enqueued_high.empty()||!_enqueued_low.empty())
        beginService();
}

void CompositeQueue::doNextEvent() {
    completeService();
}

// 处理 ECN 标记的辅助函数（入队或出队时调用）
void CompositeQueue::mark_ECN(Packet& pkt, bool on_enqueue) {
    // 检查当前调用时机是否与配置一致
    // on_enqueue=true 表示当前在入队时调用，on_enqueue=false 表示在出队时调用
    if (on_enqueue != _ecn_mark_on_enqueue) {
        return;  // 时机不匹配，不执行标记
    }

    // 使用 decide_ECN 函数判断是否需要标记 ECN
    int ecn_decision = decide_ECN();

    if (ecn_decision == ECN_MARK) {
        uint32_t old_flags = pkt.flags();
        bool already_marked = (old_flags & _ecn_tag) == _ecn_tag;

        pkt.set_flags(old_flags | _ecn_tag);

        // 只在启用 ECN notify 回传时才发送通知包
        if (_enable_ecn_notify && !already_marked && pkt.type() == UECDATA) {
            UecDataPacket* uec_pkt = static_cast<UecDataPacket*>(&pkt);
            uint32_t ecn_notify_dst = uec_pkt->get_src();
            uint32_t ecn_notify_flow_id = uec_pkt->get_sink_flow_id();

            if (ecn_notify_dst != UINT32_MAX && ecn_notify_flow_id != 0) {
                double we_w_ratio = (_w > 0) ? (_we / _w) : 0;
                mem_b queue_capacity = maxsize();
                UecEcnNotifyPacket* ecn_notify = UecEcnNotifyPacket::newpkt(
                    pkt.flow(), ecn_notify_dst,
                    ecn_notify_flow_id, pkt.pathid(),
                    _queuesize_low, _queuesize_high, _ecn_tag,
                    we_w_ratio,
                    uec_pkt->epsn(),  // Pass the PSN of the packet that triggered CNP
                    getDqDt(),  // Pass the queue depth change rate
                    queue_capacity  // Pass the queue capacity
                );
                _switch->receivePacket(*ecn_notify);

                const char* timing_str = on_enqueue ? "On Enqueue" : "On Dequeue";
                cout << "[ECN Notify " << timing_str << "] queue_id=" << _queue_id
                    << " _queuesize_low=" << _queuesize_low
                    << " _queuesize_high=" << _queuesize_high
                    << " ecn_tag=" << _ecn_tag
                    << " w=" << _w
                    << " we=" << _we
                    << " we_w_ratio=" << we_w_ratio
                    << " cnp_psn=" << uec_pkt->epsn()
                    << " dq_dt=" << getDqDt()  // Pass the queue depth change rate
                    << endl;
            }
        }
    } else if (_nscc_fastcn && ecn_decision == ECN_LOW_WATERMARK) {
        // 低于 low 水线的特殊处理（如需要）
        // 当前不执行任何操作
        // 只在启用 ECN notify 回传时才发送通知包
        if (_enable_ecn_notify && pkt.type() == UECDATA) {
            UecDataPacket* uec_pkt = static_cast<UecDataPacket*>(&pkt);
            uint32_t ecn_notify_dst = uec_pkt->get_src();
            uint32_t ecn_notify_flow_id = uec_pkt->get_sink_flow_id();

            if (ecn_notify_dst != UINT32_MAX && ecn_notify_flow_id != 0) {
                double we_w_ratio = (_w > 0) ? (_we / _w) : 0;
                mem_b queue_capacity = maxsize();
                UecEcnNotifyPacket* ecn_notify = UecEcnNotifyPacket::newpkt(
                    pkt.flow(), ecn_notify_dst,
                    ecn_notify_flow_id, pkt.pathid(),
                    _queuesize_low, _queuesize_high, _ecn_tag,
                    we_w_ratio,
                    uec_pkt->epsn(),  // Pass the PSN of the packet that triggered CNP
                    getDqDt(),  // Pass the queue depth change rate
                    queue_capacity  // Pass the queue capacity
                );
                _switch->receivePacket(*ecn_notify);

                const char* timing_str = on_enqueue ? "On Enqueue" : "On Dequeue";
                cout << "[ECN Notify " << timing_str << "] queue_id=" << _queue_id
                    << " _queuesize_low=" << _queuesize_low
                    << " _queuesize_high=" << _queuesize_high
                    << " ecn_tag=" << _ecn_tag
                    << " w=" << _w
                    << " we=" << _we
                    << " we_w_ratio=" << we_w_ratio
                    << " cnp_psn=" << uec_pkt->epsn()
                    << " dq_dt=" << getDqDt()  // Pass the queue depth change rate
                    << endl;
            }
        }
    }
}

void CompositeQueue::receivePacket(Packet& pkt)
{
    if (_queue_id == DEBUG_QUEUE_ID)
    {
        cout << timeAsUs(eventlist().now()) << " name " << _nodename << " arrive "
             << _queuesize_low * 8 / ((_bitrate / 1000000.0)) << " _queueid " << _queue_id << " switch " << _switch->getID() 
             <<" flowid " << pkt.flow_id() << " ev " << pkt.pathid()<< endl;
    }
    
    // ========== 在网时延统计 ==========
    // 只统计低优先级的数据包（非 header_only 的数据包）
    // 检查是否是 stor 交换机的发送队列 (LS->US，即 ToR 到 Agg 的上行队列)
    // 队列名称格式为 "LS{X}->US{Y}(Z)"
    if (!pkt.header_only() &&
        _nodename.find("LS") != string::npos && 
        _nodename.find("->US") != string::npos) {
        // 这是 stor 交换机的发送队列，记录数据包进入 stor 的时间
        pkt.set_stor_enqueue_time(eventlist().now());
    }
    // ==================================
    
    pkt.flow().logTraffic(pkt,*this,TrafficLogger::PKT_ARRIVE);
    if (_logger) _logger->logQueue(*this, QueueLogger::PKT_ARRIVE, pkt);

    if (!pkt.header_only()){
        if (_queuesize_low+pkt.size() <= _maxsize  || drand()<0.5) {
            //regular packet; don't drop the arriving packet

            // we are here because either the queue isn't full or,
            // it might be full and we randomly chose an
            // enqueued packet to trim
            
            // 处理 ECN 标记（根据配置在入队或出队时）
            mark_ECN(pkt, true);  // true 表示入队时调用
            
            if (_queuesize_low+pkt.size()>_maxsize){
                // we're going to drop an existing packet from the queue
                if (_enqueued_low.empty()){
                    //cout << "QUeuesize " << _queuesize_low << " packetsize " << pkt.size() << " maxsize " << _maxsize << endl;
                    assert(0);
                }
                //take last packet from low prio queue, make it a header and place it in the high prio queue
                Packet* booted_pkt = _enqueued_low.pop_front();
                _queuesize_low -= booted_pkt->size();
                if (_logger) _logger->logQueue(*this, QueueLogger::PKT_UNQUEUE, *booted_pkt);

                if (_disable_trim) {
                    booted_pkt->free();
                    _num_drops++;
                    cout << "A [ " << _enqueued_low.size() << " " << _enqueued_high.size() << " ] DROP "
                         << " flowid " << booted_pkt->flow_id()<< endl;
                } else {
                    // cout << "A [ " << _enqueued_low.size() << " " << _enqueued_high.size() << " ] STRIP" << endl;
                    // cout << "booted_pkt->size(): " << booted_pkt->size();
                    booted_pkt->strip_payload(_trim_size);
                    // cout << "CQ trim at " << _nodename << endl;
                    _num_stripped++;
                    booted_pkt->flow().logTraffic(*booted_pkt, *this, TrafficLogger::PKT_TRIM);
                    if (_logger)
                        _logger->logQueue(*this, QueueLogger::PKT_TRIM, pkt);

                    if (_queuesize_high + booted_pkt->size() > 2 * _maxsize) {
                        if (_return_to_sender && booted_pkt->reverse_route() && booted_pkt->bounced() == false) {
                            // return the packet to the sender
                            if (_logger)
                                _logger->logQueue(*this, QueueLogger::PKT_BOUNCE, *booted_pkt);
                            booted_pkt->flow().logTraffic(pkt, *this, TrafficLogger::PKT_BOUNCE);
                            // XXX what to do with it now?
#if 0
                            printf("Bounce2 at %s\n", _nodename.c_str());
                            printf("Fwd route:\n");
                            print_route(*(booted_pkt->route()));
                            printf("nexthop: %d\n", booted_pkt->nexthop());
#endif
                            booted_pkt->bounce();
#if 0
                            printf("\nRev route:\n");
                            print_route(*(booted_pkt->reverse_route()));
                            printf("nexthop: %d\n", booted_pkt->nexthop());
#endif
                            _num_bounced++;
                            booted_pkt->sendOn();
                        } else {
                            booted_pkt->flow().logTraffic(*booted_pkt, *this, TrafficLogger::PKT_DROP);
                            booted_pkt->free();
                            if (_logger)
                                _logger->logQueue(*this, QueueLogger::PKT_DROP, pkt);
                        }
                    } else {
                        _enqueued_high.push(booted_pkt);
                        _queuesize_high += booted_pkt->size();
                        if (_logger)
                            _logger->logQueue(*this, QueueLogger::PKT_ENQUEUE, *booted_pkt);
                    }
                }
            }

            //assert(_queuesize_low+pkt.size()<= _maxsize);
            Packet* pkt_p = &pkt;
            _enqueued_low.push(pkt_p);
            _queuesize_low += pkt.size();
            if (_logger) _logger->logQueue(*this, QueueLogger::PKT_ENQUEUE, pkt);
            
            if (_serv==QUEUE_INVALID) {
                beginService();
            }
            
            //cout << "BL[ " << _enqueued_low.size() << " " << _enqueued_high.size() << " ]" << endl;
            
            return;
        } else {
            if (_disable_trim) {
                if (_queue_id == DEBUG_QUEUE_ID) {
                    cout <<timeAsUs(eventlist().now()) << "B[ " << _enqueued_low.size() << " "
                         << _enqueued_high.size() << " ] DROP " << pkt.flow().flow_id() << " queue "
                         << str() << " pathid " <<pkt.pathid()<< " queueid " << _queue_id
                         << " size " << pkt.size() << endl;
                }
                pkt.free();
                _num_drops++;
                return;
            }
            //strip packet the arriving packet - low priority queue is full
            //cout << "B [ " << _enqueued_low.size() << " " << _enqueued_high.size() << " ] STRIP" << endl;
            pkt.strip_payload(_trim_size);
            //cout << "CQ trim at " << _nodename << endl;
            _num_stripped++;
            pkt.flow().logTraffic(pkt,*this,TrafficLogger::PKT_TRIM);
            if (_logger) _logger->logQueue(*this, QueueLogger::PKT_TRIM, pkt);
        }
    }
    assert(pkt.header_only());
    
    if (_queuesize_high+pkt.size() > 2*_maxsize) {
        //drop header
        //cout << "drop!\n";
        if (_return_to_sender && pkt.reverse_route()  && pkt.bounced() == false) {
            //return the packet to the sender
            if (_logger) _logger->logQueue(*this, QueueLogger::PKT_BOUNCE, pkt);
            pkt.flow().logTraffic(pkt,*this,TrafficLogger::PKT_BOUNCE);
            //XXX what to do with it now?
#if 0
            printf("Bounce1 at %s\n", _nodename.c_str());
            printf("Fwd route:\n");
            print_route(*(pkt.route()));
            printf("nexthop: %d\n", pkt.nexthop());
#endif
            pkt.bounce();
#if 0
            printf("\nRev route:\n");
            print_route(*(pkt.reverse_route()));
            printf("nexthop: %d\n", pkt.nexthop());
#endif
            _num_bounced++;
            pkt.sendOn();
            return;
        } else {
            if (_logger) _logger->logQueue(*this, QueueLogger::PKT_DROP, pkt);
            pkt.flow().logTraffic(pkt,*this,TrafficLogger::PKT_DROP);
            cout << "B[ " << _enqueued_low.size() << " " << _enqueued_high.size() << " ] DROP " 
                 << pkt.flow().flow_id() << endl;
            pkt.free();
            _num_drops++;
            return;
        }
    }
    
    
    //if (pkt.type()==NDP)
    //  cout << "H " << pkt.flow().str() << endl;
    Packet* pkt_p = &pkt;
    _enqueued_high.push(pkt_p);
    _queuesize_high += pkt.size();
    if (_logger) _logger->logQueue(*this, QueueLogger::PKT_ENQUEUE, pkt);
    
    //cout << "BH[ " << _enqueued_low.size() << " " << _enqueued_high.size() << " ]" << endl;
    
    if (_serv==QUEUE_INVALID) {
        beginService();
    }
}

mem_b CompositeQueue::queuesize() const {
    return _queuesize_low + _queuesize_high;
}

// QueueStatsTimer implementation
QueueStatsTimer::QueueStatsTimer(CompositeQueue* queue, EventList& eventlist)
    : EventSource(eventlist, "QueueStatsTimer"), _queue(queue)
{
    _interval = 5000000;  // 5 microseconds in picoseconds
    _next_stats_time = eventlist.now() + _interval;

    // Initialize we to bandwidth * RTT (BDP) during construction
    // we represents the bandwidth-delay product in bytes
    linkspeed_bps bitrate = _queue->_bitrate;
    simtime_picosec rtt = CompositeQueue::getNetworkRtt();
    // BDP = bitrate * RTT / 8 (convert bits to bytes)
    double bdp = timeAsSec(rtt) * (bitrate / 8.0);
    // Add 4KB to we
    _queue->setWe(bdp + 4096);

    // Initialize previous queue depth
    _last_q_low = _queue->_queuesize_low;

    eventlist.sourceIsPending(*this, _next_stats_time);
}

void QueueStatsTimer::doNextEvent()
{
    // Get current simulation time
    simtime_picosec now = eventlist().now();

    // Read queue depth from the queue
    mem_b q_low = _queue->_queuesize_low;

    // Get queue parameters
    linkspeed_bps bitrate = _queue->_bitrate;
    simtime_picosec rtt = CompositeQueue::getNetworkRtt();

    // Calculate dq/dt (queue depth change rate in bytes/second)
    // dt is the fixed sampling interval
    double dt = timeAsSec(_interval);  // seconds
    double dq = q_low - _last_q_low;  // queue depth change in bytes
    double dq_dt = dq / dt;  // bytes per second

    // Convert bitrate to bytes per second
    double bitrate_bytes_per_sec = bitrate / 8.0;

    // Calculate w using the formula: (dq/dt + bitrate) * (q/bitrate + rtt)
    // Term 1: (dq/dt + bitrate)
    double term1 = dq_dt + bitrate_bytes_per_sec;

    // Term 2: (q/bitrate + rtt)
    double q_over_bitrate = 0.0;
    if (bitrate_bytes_per_sec > 0) {
        q_over_bitrate = q_low / bitrate_bytes_per_sec;
    }
    double term2 = q_over_bitrate + timeAsSec(rtt);

    // Final w value
    double w = term1 * term2;

    // Update the queue's w value
    _queue->setW(w);

    // Update the queue's dq_dt value
    _queue->setDqDt(dq_dt);

    // Update previous queue depth for next iteration
    _last_q_low = q_low;

    // Schedule next stats event
    _next_stats_time = now + _interval;
    eventlist().sourceIsPending(*this, _next_stats_time);
    // cout << "time=" << now << " QueueStatsTimer::doNextEvent() w=" << w << " we=" << _queue->_we << " dq_dt=" << dq_dt << endl;
}
