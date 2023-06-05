---
title: 'RDMA Notes'
date: 2023-06-05
permalink: /posts/2023/06/rdma-notes/
tags:
  - rdma
  - network
---
# 参考资料
本笔记主要参考了知乎的《RDMA杂谈》一文：[https://zhuanlan.zhihu.com/p/164908617](https://zhuanlan.zhihu.com/p/164908617)
其他参考资料主要为IB协议。
可供参考的资料有：

- OFA官网培训PPT [https://www.openfabrics.org/training/](https://www.openfabrics.org/training/)
- Mellanox提供的编程手册《RDMA Aware Networks Programming User Manual》
- RDMA博客 [https://www.rdmamojo.com/](https://www.rdmamojo.com/)
# RDMA概述

- DMA帮助CPU摆脱从内存到IO的压力
- RDMA让DMA扩展到远程
- RDMA优势： 
   - 0拷贝：用户空间和内核空间不进行拷贝。TCP中，应用层到kernel有一次payload拷贝，传输层到网络层有一次socket buffer（skb）拷贝，网络层到用户态driver是指针传递无拷贝，用户态driver封装后通过dma给网卡也是一次拷贝。所以TCP一共三次拷贝，而RDMA一共只有DMA的一次拷贝。
   - 内核Bypass：数据流程绕过内核
![[Pasted image 20230520143816.png]]
# 比较基于传统以太网域RDMA技术的通信

- RDMA分为控制通路和数据通路，控制通路需要进入内核态准备通信所需的内存资源
- RDMA的数据收发绕过了内核并且数据交换过程并不需要CPU参与，报文的组装和解析是由硬件完成的。
# RDMA基本元素
| 缩略语 | 全称 | 备注 |
| --- | --- | --- |
| WQ | Work Queue | 存放任务书WQE的FIFO |
| WQE | Work Queue Entry | 软件下发给硬件的任务说明 |
| QP | Queue Pair | 一对Work Queue，包括一个SQ和一个RQ。QP是RDMA通信的基本单元（而不是节点） |
| QPN | Qeeue Pair Number | 每个节点上的每个QP都有的唯一的编号，可以唯一确定一个节点上的QP |
| QPC | Queue Pair Context | 记录QP信息的表 |
| SQ | Send Queue | WQ的实例 |
| RQ | Reveive Queue | WQ的实例 |
| SRQ | Shared Receive Queue | 使用RQ的情况远小于SQ，所以多个QP共享一个SRQ来节省内存 |
| CQ | Completion Queue | 任务报告的FIFO队列 |
| CQE | Completion Queue Entry | 硬件完成任务后返回给软件的“任务报告” |
| WR | Work Request | “工作请求”，是WQE在用户层的映射 |
| WC | Work Completion | “工作完成”，CQE在用户层的映射 |
| MR | Memory Region |  |
| HCA | Host Channel Adapter | 即RDMA硬件 |

**注意**：

- WQE和CQE都不对用户可见，是驱动中的概念，用户通过API下发WR，并收到WC。
- 对于SEND或RDMA Write请求，在数据被写入接收方内存之前HCA可能已经回复ACK，如果后续把数据写入内存时出错，接收方会通知上层用户出错（可能通过WC），但不会通知实际发送方。如何处理由接收方决定。发送方接收到ACK后就认为对端收到了（ACK仅仅表示数据已经成功到达响应节点的容错域（Fault））。
- RDMA技术中的QP的模型就是需要保序的，单个QP不能并行发送消息，WQE必须按序处理。如果传输不互相关联，那么应该创建多个QP来满足并行的需求。
- Send-Recv过程中发送端并不知道发送的数据会放到哪里，接收端下发的WQE告知硬件收到的数据需要放到哪个地址。
![Pasted image 20230520152359.png](https://cdn.nlark.com/yuque/0/2023/png/36097650/1685933323340-55e621e4-7898-490f-a4fd-cd9b5b9a3668.png#averageHue=%23eae9e9&clientId=u617dffe6-8d2e-4&from=drop&id=u9f637bca&originHeight=896&originWidth=1568&originalType=binary&ratio=1.5&rotation=0&showTitle=false&size=434246&status=done&style=none&taskId=u33108d1e-9051-43f2-b0fa-7a18fead047&title=)
# RDMA操作类型
## Send & Receive

- 双端操作，需要双端CPU参与。
- Send时，对端CPU先建立RQ中的WQE，然后本端才发送SQ的WQE。
- 发送端不知道发送的数据会被存放在哪里，因此Send操作不会附带RETH中的虚拟地址。放在哪里完全取决于接收端提前准备好的Buffer在哪。
- 发送完成时提交CQE。而Write和Read不触发CQE，除非Write with imm。
## Write

- write是本端主动写入远端内存的行为，除了准备阶段，远端CPU不需要参与，也不感知何时有数据写入、何时接受完毕。所以**write是单端操作**。
- write在准备阶段获取对端某一片可用内存的地址和密钥，即获取读写权限，然后像访问自己内存一样访问远端内存区域。拿到密钥需要远端CPU许可。许可授权后，CPU不再参与数据收发过程。
- 本端通过虚拟地址读写远端内存。在write中，WQE里面是虚拟地址，网卡负责转换WQE里面的虚拟地址到物理地址，然后从硬件里拿数据组装发送；响应端解析数据包中的目的虚拟地址，
## Read

- Read和Write一样都携带一个虚拟地址。Write First和Read Request都含有RETH扩展头：![Pasted image 20230520191012.png](https://cdn.nlark.com/yuque/0/2023/png/36097650/1685933336051-0f87989b-43fa-49d8-9510-a7bd2b23fad2.png#averageHue=%23eeedec&clientId=u617dffe6-8d2e-4&from=drop&id=u2bff2851&originHeight=262&originWidth=1135&originalType=binary&ratio=1.5&rotation=0&showTitle=false&size=82064&status=done&style=none&taskId=u304d38bb-c900-49d3-a74e-fce37fc5443&title=)
**注意**：
- Send和Receive的收、发过程需要有对端主动参与，而Read和Write的读写是本端对一个没有主动性的对端进行的操作的语义。
- 可靠连接的Read和Write在对端也有QP。对端的QP不需要RQ WQE来接受消息，但是QP实体存在，硬件会根据报文中的QPN找到本地的QPC和连接信息进行校验。
- key的交换不局限于途径，可以通过Send/receive或者socket连接。
- Read请求慢于Write。
- Read时，本地会暂存Read请求的控制信息，等待对端回复Response
# RDMA基本服务类型
RDMA通信的核心仍然是IB协议。**RDMA的基本通信单元是QP**，而基于QP的通信模型有很多种，我们在RDMA领域称其为“服务类型”。IB协议中通过“可靠”和“连接”两个维度来描述一种服务类型。
## 可靠与不可靠

- 可靠服务在发送和接受者之间保证了信息最多只会传递一次，并且能够保证其按照发送顺序完整的被接收
- 对于可靠服务，有三种机制确保其可靠。对于不可靠服务，没有机制保证数据包被正确接收。
### ACK应答

- 在IB协议的可靠服务类型中，使用了应答机制来保证数据包被对方收到。
- IB的可靠服务类型中，接收方不是每一个包都必须回复，也可以一次回复多个包的ACK。
### 数据校验

- IB使用CRC来保证数据包没有差错。
- CRC校验不通过的数据包会被丢弃。
- RoCEv2中，UDP校验被直接置0，IP的校验（ICRC）起校验作用
### 保序机制

- IB协议中有PSN（Packet Sequence Number，包序号）的概念，即每个包都有一个递增的编号。
- PSN可以用来检测是否丢包，比如收端收到了1，但是在没收到2的情况下就收到了3，那么其就会认为传输过程中发生了错误，在收到3之后会回复一个NAK给发端，让其重发丢失的包。
## 连接与数据报
### 连接

- 对于基于连接的服务来说，每个QP都和另一个远端节点相关联。在这种情况下，QP Context（QPC）中包含有远端节点的QP信息。在建立通信的过程中，两个节点会交换包括稍后用于通信的QP在内的对端信息
![v2-320b1db2b90c5334cb4200a0784a12ce_720w.webp](https://cdn.nlark.com/yuque/0/2023/webp/36097650/1685933355588-f07e8ee2-ed22-4b2d-a7c7-cb1179868f24.webp#averageHue=%23fdfefb&clientId=u617dffe6-8d2e-4&from=drop&id=u9c6e99b0&originHeight=417&originWidth=720&originalType=binary&ratio=1.5&rotation=0&showTitle=false&size=18792&status=done&style=none&taskId=u43913690-a24b-415d-876a-a64575e1505&title=)
- 连接服务类型中的每个QP，都和唯一的另一个QP建立了连接，也就是说QP下发的每个WQE的目的地都是唯一的。
- 连接的维护就是QPC里面的记录，断开连接只需要修改QPC内容。
## 服务类型

- 对于RC，如果N个机器要通信，必须建立`N*(N-1)`个QP以上，因为QP必须一一配对。
- 对于UD，每个机器有一个QP即可，因为每次UD通信前都会重新传输控制信息，UD也不要求必须单对单传输
**注意**：
- 对端收到数据包后会使用相同的算法计算出本端计算的校验值进行对比，如果不一致则会在IB Link Layer抛弃掉（因为通常ICRC出问题时，There is nothing can be trusted in the packet, including the PSN it carries）（但是RoCEv2中没有IB Link Layer），所以如果PSN 10的包Corrupted了，那么应用层只会收到PSN为9和11的包，PSN 11的包会触发IB Transport Layer to initiate NAK。
- 对于PSN 9 11的两个连续包，IB Transport Layer不会等待PSN 10的包，而是收到PSN 11后立即发送NAK with PSN 11。
- 在标准协议中，同一连接（一对QP）只应该使用同一条路径，路径变化后需要通过NAK等保序。源目的IP、MAC、端口号都是不变的，路径理论始终一致（ECMP）
- RDMA的PMTU（Path MTU）最大为4096，区别于网卡的MTU，如果时RoCEv2协议，PMTU大于MTU时将在以太网层被再次拆包。RC最大消息长度很大，但是不是一次发出的，要在IB传输层被拆成最大4096的包。
# Memory Region (MR)

- APP提供的地址都是虚拟地址（VA），经过MMU的转换才能得到真实的物理地址（PA），RDMA网卡是如何得到PA从而去内存中拿到数据的呢？
- 就算网卡知道上哪去取数据，如果用户恶意指定了一个非法的VA，那网卡岂不是有可能被“指使”去读写关键内存？
## 定义Memory Region

- RDMA网卡只能访问已经由用户向系统申请并且被注册为Memory Region的内存区域。
## Memory Region的作用
### 虚实地址转换

- APP只能看到VA，所以WQE里传给HCA的也是VA。Write First和Read Request里面的RETH里面的地址都是VA。
- 而HCA在总线上，无法看到TLB和页表，所以不能利用他们实现PA和VA转化。
- 注册MR的过程中，硬件会在内存中创建并填写一个VA to PA的映射表，这样需要的时候就能通过查表把VA转换成PA了。
- 如果左侧要向右侧进行RDMA WRITE： 
   - 图中两端都已经完成了注册MR的动作，MR即对应图中的“数据Buffer”，同时也创建好了VA->PA的映射表。
   - 首先本端APP会下发一个WQE给HCA，告知HCA，用于存放待发送数据的本地Buffer的虚拟地址，以及即将写入的对端数据Buffer的虚拟地址。
   - 本端HCA查询VA->PA映射表，得知待发数据的物理地址，然后从内存中拿到数据，组装数据包并发送出去。
   - 对端HCA收到了数据包，从中解析出了目的VA。
   - 对端HCA通过存储在本地内存中的VA->PA映射表，查到真实的物理地址，核对权限无误后，将数据存放到内存中。

![Pasted image 20230112120730.jpg](https://cdn.nlark.com/yuque/0/2023/jpeg/36097650/1685933373995-c0558ca3-9118-43cf-90e6-e485b751f906.jpeg#averageHue=%23fefefb&clientId=u617dffe6-8d2e-4&from=drop&id=uf83f7c9b&originHeight=297&originWidth=554&originalType=binary&ratio=1.5&rotation=0&showTitle=false&size=33764&status=done&style=none&taskId=ua66283e4-74c6-43ba-8ce0-7f21294feea&title=)

- 注意： 
   - 地址转换和写入内存都无需CPU参与，只是MR建立时查表。
   - RDMA WRITE和READ都需要提前建立MR。
### 产生密钥控制权限

- 用户注册MR的动作会产生两把钥匙——L_KEY（Local Key）和R_KEY（Remote Key）
- 本地HCA持L_KEY可以访问本地内存的MR。本地HCA持远端HCA的R_KEY可以访问远端内存的MR（在RETH扩展头中）。
- RMDA通信前会通过其他方式建立链路，交换RDMA通信所必须的信息，比如VA、KEY、QPN（Queue Pair Number）。
### 避免操作系统换页

- 操作系统会换页，操作系统有页表而网卡没有，换页会导致PA-VA映射失效。
- MR会pin住内存区域，使其长期不被换页直到用户主动注销MR。
**注意**：
- L_Key和R_Key都是32位的，分为24 bits的index和8 bits的Key。Index是硬件寻找MR Context的索引，Key用来校验访问权限。一般Index递增，Key随机。
- MR和QP一样，都是属于一个进程的被隔离的资源，QP和MR之间是独立关系，一个QP可以关联多个MR，一个MR也可以被多个QP关联。QP和MR之间通过PD（Protection Domain）产生关联。
- 用户malloc申请内存，然后用ibv_reg_mr注册MR。注销的时候反过来调用ibv_dereg_mr，然后调用free即可释放内存。
# Protection Domain (PD)

- 远端节点只要知道本端的VA和R_Key就可以访问本段某个MR的内容，为了隔离资源的权限，把每个节点划分为不同的PD。
- IB协议规定，每个Node节点必须至少有一个PD，每个QP都必须属于一个PD，每个MR也必须属于一个PD。
- PD是一个软件实体的结构体。记录了保护域的信息。初始化QP和MR时，必须传入PD的指针/句柄。
- PD是本地概念，对于其他节点是不可见的，MR对于本端和对端都可见。
- PD的作用主要是隔离保护，如下图，QP8不能和MR1通信，因为：首先，QP8只能和QP3建立连接，不能连接到QP6进而和MR1访问；其次，由于PD0的存在，QP3只能访问MR0，不能访问MR1.
![Pasted image 20230521171645.png](https://cdn.nlark.com/yuque/0/2023/png/36097650/1685933469568-aca8bff7-2b61-4d50-a7ce-4a237a6dacb9.png#averageHue=%23f3dccb&clientId=u617dffe6-8d2e-4&from=drop&id=uaa3e70bb&originHeight=655&originWidth=768&originalType=binary&ratio=1.5&rotation=0&showTitle=false&size=151653&status=done&style=none&taskId=ud0d42b52-ce4d-4020-9a81-df53b3733fc&title=)

**注意**：

- 一个QP或者MR不能属于不同的PD。
# Address Handle (AH)

- AH意为地址句柄，主要用在UD等服务类型中，本端通过使用AH来指定对端节点
- 对于RC，两端有连接，对端信息存储在QP Context中，不易丢失。而UD没有链接，在IB协议中GID（Global Identifier）替代了IP的地位，需要有一个通讯录地址簿来查找一个节点的GID。
- 用户不是直接把对端的地址信息GID填到WQE中的，而是提前准备了一个地址簿，每次通过一个索引来指定对端节点的地址信息，这个索引就是AH。每个目的节点都创建一个AH，而AH可以被多个QP公用。
- UD通信前，用户要为每个可能的对端节点创建AH（**AH是用户调用Verbs API创建的**），AH被驱动放到系统内存并返回索引句柄。
- AH和QP、MR一样，都通过PD进行资源划分，不同PD间的AH不能相互访问，如下图所示：
![Pasted image 20230527153935.png](https://cdn.nlark.com/yuque/0/2023/png/36097650/1685933481018-ba2913b8-778e-421f-b77c-0d20b00967bc.png#averageHue=%23d7dddc&clientId=u617dffe6-8d2e-4&from=drop&id=u10505995&originHeight=234&originWidth=520&originalType=binary&ratio=1.5&rotation=0&showTitle=false&size=60828&status=done&style=none&taskId=ue1fe3dae-43fe-4a5f-ad61-c8c6bc746c9&title=)
**注意**：
- RC协议不需要AH，AH是只针对UD的概念。AH中存储的是通过Socket得到的GID、QKey、RKey等。
- 对于RoCEv2来说，GID（即用户接口用的网络层地址）会转化成IPv4/IPv6地址。
- 对于RoCEv2来说，目的端口号恒为4791，源端口号一般是随机生成的。
# Queue Pair (QP)
## QPC

- QPC的概念如下图所示。
- QP是一个队列结构。在硬件上，QP是一段包含了若干个WQE的存储空间，IB网卡从这段空间中读取WQE的内容并按照用户期望去内存中取数据。IB协议没有限制这段空间在内存上还是IB板载存储空间上。软件上，QP是一个IB网卡驱动维护的数据结构，包含QP的地址指针和相关软件属性。
- 问题是：驱动程序里已经存储了QP的软件属性，为什么还要用QPC呢？
- 因为QPC是给硬件看的，也会用来在软硬件之间同步QP信息。软件存储的QP信息在虚拟地址空间中，硬件无法得知，所以需要软件提前开辟QPC空间，承载QP的起始地址、WQE数量等信息给网卡看。
- 硬件得知QPC的地址，进而解析QPC的内容，从而得知QP的位置、大小、序号等信息，进而找到QP。进而知道应该取第几个WQE处理。
![Pasted image 20230527161154.png](https://cdn.nlark.com/yuque/0/2023/png/36097650/1685933497087-4cc3cce1-9d3c-42fa-8f7d-e2b953377b77.png#averageHue=%23f9f9f9&clientId=u617dffe6-8d2e-4&from=drop&id=u5c617b9a&originHeight=1418&originWidth=1981&originalType=binary&ratio=1.5&rotation=0&showTitle=false&size=594762&status=done&style=none&taskId=ucc92ad59-78f0-40eb-919d-0ee8e17a678&title=)
## QP Number

- QPN
- 保留编号： 
   - QP 0：用于子网管理的接口SMI（Subnet management Interface）
   - QP 1：用于通用服务接口GSI（General Service Interface）。GSI是一组管理服务，其中的CM（Communication Management）服务可以在通信双方节点正式建立连接前用来交换必须信息。
## 用户接口
### 控制面

- 增：Create QP。创建QP本身和QPC等软硬件资源。初始化一系列属性包括服务类型等。
- 删：Destroy QP。释放QP全部软硬件资源。
- 改：Modify QP修改QP（和对应的QPC）的状态、路径的MTU（PMTU）等
- 查：Query QP。查询QP的状态、属性。主要来自QPC和驱动。
- 都有对应的Verbs接口。类似于`ibv_create_qp()`这种形式。
### 数据面

- 数据面上QP对上层的接口只有两种，用于向QP填写发送和接受请求（指命令QP成为一次通信过程的”发起方Requestor“和”接收方Responser“）
- 行为上都是软件向QP填写一个WQE（应用层成为WR）
- Post Send Request：表示WQE属于通信发起方。包括Send、Write和Read。
- Post Receive Request：表示WQE是通信接收方，接收端需要提前准备缓冲区并将缓冲区地址信息告知准备好的Receive WQE。只用于Send的Receive
## QP状态机
![Pasted image 20230529095624.png](https://cdn.nlark.com/yuque/0/2023/png/36097650/1685933505574-988db3d2-dc07-4b85-9cc1-04e507add6e7.png#averageHue=%23f7f6f5&clientId=u617dffe6-8d2e-4&from=drop&id=u07b3698d&originHeight=1348&originWidth=1440&originalType=binary&ratio=1.5&rotation=0&showTitle=false&size=1061609&status=done&style=none&taskId=u5f6c44c0-dc80-460c-9ba4-5437d06b318&title=)

- 绿色状态转换由Modify QP的用户接口主动触发，红色的状态是错误自动跳转，需要由Modify QP重新配置。
- 通过Create QP进入（左上角，不考虑EE概念，它属于RD服务），通过Destroy QP离开
- RST (Reset)：创建好的QP的复位状态。资源申请好但无法接受下发的WQE
- INIT (initialized)：初始化状态。可以Post Receive给QP（即下发Receive WR），但是收到的消息不会被处理，只会被丢弃；如果用户下发Post Send的WR，会报错。
- RTR (ready to receive)：在INIT的基础上，RQ可以正常工作，可以处理RQ收到的消息，但SQ仍然不能工作。
- RTS (ready to send)：在RTR的基础上，SQ也可以正常工作。进入该状态前，QP必须与对端建立连接。
- SQD (send queue drain)：发送队列排空。会将SQ中的所有WQE发送完后再处理新的WQE，这里还可以下发SQ的WQE，但是先不会被处理。
- SQEr (send queue error)：当某个Send WR需要发送完成错误（此时对应硬件通过CQE告知驱动发送错误），会导致QP进入此状态。
- ERR：其他状态下发生错误都会进入该状态，此时QP会停止处理WQE。修复错误后进入RST状态。

**注意**：

- RDMA Write和Read操作，并不会消耗对端RQ，这两种操作更符合RDMA的宗旨——不需要对端CPU参与通信。Send-Recv虽然加入了一些加速手段，但是从通信模型上看，跟传统的模型是没有区别的。
- QPC对用户不可见，与协议无关，由厂商自行设计。
- RAW QP：不带IB传输层头部的QP，使用RAW QPs进行报文传输时，数据报文格式中不包含基本传输头和扩展传输头，用户自行进行头部的定义。
- 几乎所有厂商的QP队列都在内存里，但由于DDR通信的延迟和对QPC的频繁修改，网卡一般都缓存了QPC再往卡里。如果只是运行在用户态业务的RDMA应用的话，内核态并不需要访问QP Buffer所在的内存，只需要用户态和网卡都能访问这片内存就可以了。用户态填好WQE后通知硬件，硬件从内存中取走WQE，不需要经过内核态。
# Completion Queue (CQ)
## 基本概念
### CQE的产生时间

- 可靠服务类型
   - Send：本端收到对端的ACK产生CQE，对端收到send的消息完成校验和数据存放后立即产生CQE
   - Recv：本端收到对端发来的Send，完成校验和数据存放后立即产生CQE。
   - Write：本端收到ACK产生CQE，对端不产生CQE
   - Read：本端收到带有AETH的数据包后产生CQE，对端不产生CQE
- 不可靠服务
   - 不可靠服务只支持Send-Recv操作。在Send完成后，本端立马产生CQE，在对端Recv后，立马产生CQE。
### WQ和CQ的保序

- 同一个WQ中的WQE对应的CQE是保序的，不同WQ中的WQE对应的CQE之间不一定保序。同一个QP中的SQ和RQ（也包括SRQ）不一定保序，因为他们是不同的WQ。即使多个WQ共用一个CQ，仍然可以保证每个WQ的CQE都保序：

![](https://cdn.nlark.com/yuque/0/2023/webp/36097650/1685773487695-8e493be9-e5bd-4b1d-894e-14aeb492d867.webp#averageHue=%23d7e8cb&clientId=uf2d59343-2d9b-4&from=paste&id=u345916b8&originHeight=225&originWidth=574&originalType=url&ratio=1.5&rotation=0&showTitle=false&status=done&style=none&taskId=u20e645ff-5a1a-4663-bf73-000f2434065&title=)

- 上层驱动通过CQE中指明的WQE编号得知其关联的任务。
### CQ Context (CQC)
CQ是一段存放CQE队列的空间，需要把这段空间的格式等信息通过CQC编写好，放到硬件可以读取的内存中，这片内存就是CQC
![](https://cdn.nlark.com/yuque/0/2023/webp/36097650/1685774235330-605e55f3-ff2d-4742-bc63-edaec9dcb430.webp#averageHue=%23fbfbfb&clientId=uf2d59343-2d9b-4&from=paste&id=u1afb27c0&originHeight=471&originWidth=646&originalType=url&ratio=1.5&rotation=0&showTitle=false&status=done&style=none&taskId=ud6dd8a6e-8ecd-4396-8631-317c943ed5d&title=)
### CQ Number (CQN)
CQ也有编号，用于区分不同的CQ。
## 完成错误
IB协议内有三种错误类型：

- 立即错误（immediate error），表示立即停止操作并返回给上层用户错误信息。比如明明是UD，却在Post Send的时候传入了非法的RDMA WRITE的opcode。
- 完成错误（completion error），表示通过CQE将错误信息返回给上层用户。比如下发的Send类型的WQE长时间没有收到对方的ACK，会在WQE中予以体现。
- 异步错误（asynchronous error），通过中断事件方式上报给上层用户。比如用户长期不从CQ中提取CQE，导致CQ溢出，必须通过中断通知用户（因为用户此时不提取CQE，他不能从CQE中知道报错了）。
### 完成错误的检测机制
完成错误通过在CQE中填写错误码实现上报，在通信的Requester和Responder中分别有错误检测器进行检测。
![](https://cdn.nlark.com/yuque/0/2023/webp/36097650/1685775049926-8292b31a-5377-4b79-be11-fc475b71f817.webp#averageHue=%23fdfefb&clientId=uf2d59343-2d9b-4&from=paste&id=uae1d9c6b&originHeight=196&originWidth=720&originalType=url&ratio=1.5&rotation=0&showTitle=false&status=done&style=none&taskId=u4de4c573-bc89-4e0a-aac6-12d29a58479&title=)
Requester中有本地错误检测和远端错误检测模块。本地错误检测模块对SQ中的WQE进行检测，如果出错就直接填写错误码放入CQ，不会进入通信过程。远端检测模块检测远端返回的ACK中是否含有响应端的报错，远端检测模块只对RC有用。
Responder只有本地错误检测模块。用于检测发到Responder的报文是否有问题，如果有错误，会上报一个CQE，并且会在RC中回复含有错误信息的ACK。
### 常见错误

- RC服务类型的SQ和RQ完成错误。超时等。
- Local Protection Error。本地WQE中指定的内存地址的MR不合法，使用了未注册内存的数据。
- Remote Access Error。本端没有权限读对端地址。
- Transport Retry Counter Exceeded Error。重传次数超预设次数。
- Local Access Error、Local Length Error。对端试图写入没有权限写入的内存区域或本地RQ没有足够空间接受对端发送的数据。
## 接口
### 控制面
控制面上，上层用户还是有增删改查四种接口。但是对于CQ来说，上层用户只是CQ的使用者而不是管理者，所以只能从CQ中读数据，并且只能修改CQ规格（size）而不能修改其他CQ的属性。

- 增：Create CQ。指定CQ的规格即能存多少个CQE，填写一个CQE产生时候的回调函数指针。
- 删：Destroy CQ。删除CQ、CQC、CQN。
- 改：**Resize** CQ。对于CQ，只允许修改它的大小。
- 查：Query QP。查询QP的规格和回调函数。
### 数据面
软件不知道硬件何时会将CQE放入CQ（这种接收方不知道发送方什么时候发送的模式叫做“异步”模式），要让软件获取CQE，可以有轮询和中断两种模式。
现在的网卡一般是中断+轮询的方式，根据业务负载动态切换。RDMA硬件需要把CQE传递给CPU处理，RDMA定义了两种对上层的接口`poll`和`notify`，分别对应轮询和中断。

- Poll Completion Queue：用户调用该接口后，CPU定期检查CQ里面是否存在CQE，并解析。
- Request Completion Notification：用户调用该接口后会对系统注册一个中断，当CQE放到CQ后立即触发中断给CPU。
# Shared Received Queue
# Memory Window
# Verbs
# 用户态和内核态的交互
# Soft-RoCE
## 安装

- 确认内核是否支持RXE（Soft-RoCE的软件实体）
```bash
cat /boot/config-$(uname -r) | grep RXE
```
如果CONFIG_RDMA_RXE的值为y或者m，表示当前的操作系统可以使用RXE。
否则要重新编译内核，打开：
```bash
CONFIG_INET
CONFIG_PCI
CONFIG_INFINIBAND
CONFIG_INFINIBAND_VIRT_DMA
```

- 安装软件包：
```bash
sudo apt-get install libibverbs1 ibverbs-utils librdmacm1 libibumad3 ibverbs-providers rdma-core
```
软件包的功能如下：

| 软件包名 | 主要功能 |
| --- | --- |
| libibverbs1 | ibverbs动态链接库 |
| ibverbs-utils | ibverbs示例程序 |
| librdmacm1 | rdmacm动态链接库 |
| libibumad3 | ibumad动态链接库 |
| ibverbs-providers | ibverbs各厂商用户态驱动（包括RXE） |
| rdma-core | 文档及用户态配置文件 |

- 可以使用dpkg -L 查看软件包内的内容：
```bash
dpkg -L libibverbs1
```

- 可以用`ibv_devices`查看当前系统中的RDMA设备列表，Soft-RoCE在配置后也会出现在其结果中。
- 安装iproute2，我们需要其中的rdma工具来对RXE进行配置。一般的操作系统都已经包含了，安装也很简单：
```bash
sudo apt-get install iproute2
```

- perftest是一个基于Verbs接口开发的开源RDMA性能测试工具，可以对支持RDMA技术的节点进行带宽和时延测试。相比于rdma-core自带的示例程序 ，功能更加强大，当然也更复杂。使用如下命令安装：
```bash
sudo apt-get install perftest
```
## 驱动加载

- ibv_devinfo能查到真实硬件设备，但是如果无法使用（不存在/dev/infiniband/rdma_cm设备等），可能是没有加载驱动：比如ib_cm.ko，ib_umad.ko，rdma_cm.ko，rdma_ucm.ko，以及确认下librdmacm相关的软件包是否安装
## 配置RXE网卡

- 加载内核驱动：`modprobe`用于从Linux内核中添加和移除模块
```bash
modprobe rdma_rxe
```

- 然后进行用户态配置
```bash
sudo rdma link add {soft_rdma_name} type rxe netdev {binded_device_name}
sudo rdma link add rxe_0 type rxe netdev ens33
```
`ens33`是Soft-RoCE设备绑定的网络设备名，来自`ifconfig`的网卡名。

- 也可以解除绑定
```bash
sudo rdma link del {soft_rdma_name}
```

- 用`rdma`工具查看是否添加成功 / 用`ibv_devices`查看设备GUID / 用`ibv_devinfo`查看虚拟RDMA设备信息
```bash
rdma link
ibv_devinfo -d {soft_rdma_name}
```
> 在使用`rdma link add` 错误时，原因是使用的是ubantu18.04, 内核还不支持`rdma link add`，可以使用`rxe_cfg`来添加softRoce，详细使用是通过`ifconfig` 查找自己的softRoce设备，添加设备命令为`rxe_cfg add ens32`，删除设备为`rxe_cfg remove ens32`

## perftest测试

- 远端运行
```bash
ib_{op}_bw -d rxe_0
```

- 本端运行
```bash
ib_{op}_bw -d rxe_1 {Remote IP}
```
即可测试指定Verb的性能（send、write、read、atomic）

- 可用的测试项目包括：
```
ib_atomic_bw
ib_atomic_lat
ib_read_bw
ib_read_lat
ib_send_bw
ib_send_lat
ib_write_bw
ib_write_lat
```
## 抓包

- 把两个通信的虚拟机放在主机的同一个VMNet中（VMNet 8），可以在主机的Wireshark里面抓包
- 可以直接用`tcpdump`抓4791端口：
```bash
sudo tcpdump udp port 4791
```

- 如果对物理网卡进行抓包，由于包不经过软件协议栈，可能要用厂商提供的工具，比如Mellanox的`ibdump`工具；但是`libpcap > 1.9`的时候，如果厂商支持`ib_create_flow`，也可以用`tcpdump`，目前只有Mellnaox支持。

**注意**：

- Soft-RoCE的性能不及TCP。主要是几个原因：
   - IB传输层MTU最大为4096，256 Bytes的Header + 4096 Bytes的Payload，Header所占比例较高；而TCP的MTU可以很大，相当于提高了有效载荷。
   - 网卡往往可以为TCP提供硬件加速功能。
   - Soft-RoCE用CPU去计算CRC，这是一件很慢的事情。
- 这里提供我能想到的提升性能的思路：
   - 在编程时做多线程，每个线程绑定一个核，并且每个线程间不要共享使用QP，因为会出现抢锁。
   - 使用WR List代替单个WR，即每次Post Send时下发多个WR组成的WR链表，减少敲Doorbell时的系统调用开销。
   - 将网卡的MTU值设置为大于4096 + 256，可以避免链路层切包的开销。
   - 如果是RXE对接测试，可以通过修改RXE驱动关闭CRC校验，并提高RoCE的MTU值，但是这样违反了协议，貌似没什么意义。
- 要把RoCE移植到FPGA里，可以先在FPGA上的ARM核实现对链路层之上数据的处理，可以基于Soft-RoCE实现
- 即使使用了Soft-RoCE，两台设备仍然无法通过无线局域网通信。因为Wi-Fi的链路层协议不是以太网，而RoCE基于以太网。
# PyVerbs
## 下载
将该仓库克隆到机器中：
```bash
git clone https://github.com/linux-rdma/rdma-core.git
```
## 部署
编译Soft-RoCE：
```bash
./build.sh
```
必须注意是否出现`Found cython: /home/...`，否则编译出来的内容不含有Pyverbs。注意这里要先把`PATH`里面Xilinx相关内容屏蔽掉（），因为Vitis的开发套件中自带了CMake，使用其自带的CMake无法编译项目。
```bash
export PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
source ./.bashrc # 这是为了加载Conda
```
编译后，会在`~\rdma-core\build`目录下生成一个python，需要将其export为PYTHONPATH或每次运行soft-roce的python脚本时指定PYTHONPATH。比如执行示例程序：
```bash
cd ~/rdma-core/pyverbs/example
PYTHONPATH=../../build/python ./ib_devices.py
```
`rdma-core/build/bin/run_tests.py`目录下体提供了测试用例，比如测试QP：
```bash
PYTHONPATH=../../build/python ./run_tests.py --dev rxe_0 -v test_qp
```
其结果如下：
```
(base) ame@user-7049GP-TRT:~/rdma-core/build/bin$ PYTHONPATH=../../build/python ./run_tests.py --dev rxe_101_eno1 -v test_qp
test_create_raw_qp_ex_no_attr (tests.test_qp.QPTest)
Test Raw Packet QP creation via ibv_create_qp_ex without a QPAttr object ... skipped 'To Create RAW QP must be done by root on Ethernet link layer'
test_create_raw_qp_ex_with_attr (tests.test_qp.QPTest)
Test Raw Packet QP creation via ibv_create_qp_ex with a QPAttr object ... skipped 'To Create RAW QP must be done by root on Ethernet link layer'
test_create_raw_qp_ex_with_illegal_caps_max_recv_sge (tests.test_qp.QPTest)
Test Raw Packet QP creation via ibv_create_qp_ex with a QPAttr object with illegal max_recv_sge. ... ok
test_create_raw_qp_ex_with_illegal_caps_max_recv_wr (tests.test_qp.QPTest)
Test Raw Packet QP creation via ibv_create_qp_ex with a QPAttr object with illegal max_recv_wr. ... ok
test_create_raw_qp_ex_with_illegal_caps_max_send_sge (tests.test_qp.QPTest)
Test Raw Packet QP creation via ibv_create_qp_ex with a QPAttr object with illegal max_send_sge. ... ok
test_create_raw_qp_ex_with_illegal_caps_max_send_wr (tests.test_qp.QPTest)
Test Raw Packet QP creation via ibv_create_qp_ex with a QPAttr object with illegal max_send_wr. ... ok
test_create_raw_qp_no_attr (tests.test_qp.QPTest)
Test RAW Packet QP creation via ibv_create_qp without a QPAttr object ... skipped 'To Create RAW QP must be done by root on Ethernet link layer'
test_create_raw_qp_with_attr (tests.test_qp.QPTest)
Test RAW Packet QP creation via ibv_create_qp with a QPAttr object ... skipped 'To Create RAW QP must be done by root on Ethernet link layer'
test_create_rc_qp_ex_no_attr (tests.test_qp.QPTest)
Test RC QP creation via ibv_create_qp_ex without a QPAttr object ... skipped 'Create RC QP without extended attrs is not supported'
test_create_rc_qp_ex_with_attr (tests.test_qp.QPTest)
Test RC QP creation via ibv_create_qp_ex with a QPAttr object provided. ... ok
test_create_rc_qp_no_attr (tests.test_qp.QPTest)
Test RC QP creation via ibv_create_qp without a QPAttr object provided. ... ok
test_create_rc_qp_with_attr (tests.test_qp.QPTest)
Test RC QP creation via ibv_create_qp with a QPAttr object provided. ... ok
test_create_uc_qp_ex_no_attr (tests.test_qp.QPTest)
Test UC QP creation via ibv_create_qp_ex without a QPAttr object ... ok
test_create_uc_qp_ex_with_attr (tests.test_qp.QPTest)
Test UC QP creation via ibv_create_qp_ex with a QPAttr object provided. ... skipped 'Create UC QP with extended attrs is not supported'
test_create_uc_qp_no_attr (tests.test_qp.QPTest)
Test UC QP creation via ibv_create_qp without a QPAttr object provided. ... ok
test_create_uc_qp_with_attr (tests.test_qp.QPTest)
Test UC QP creation via ibv_create_qp with a QPAttr object provided. ... ok
test_create_ud_qp_ex_no_attr (tests.test_qp.QPTest)
Test UD QP creation via ibv_create_qp_ex without a QPAttr object ... skipped 'Create UD QP without extended attrs is not supported'
test_create_ud_qp_ex_with_attr (tests.test_qp.QPTest)
Test UD QP creation via ibv_create_qp_ex with a QPAttr object provided. ... skipped 'Create UD QP with extended attrs is not supported'
test_create_ud_qp_no_attr (tests.test_qp.QPTest)
Test UD QP creation via ibv_create_qp without a QPAttr object provided. ... ok
test_create_ud_qp_with_attr (tests.test_qp.QPTest)
Test UD QP creation via ibv_create_qp with a QPAttr object provided. ... ok
test_modify_ud_qp (tests.test_qp.QPTest) ... skipped 'Create UD QP without extended attrs is not supported'
test_query_data_in_order (tests.test_qp.QPTest)
Queries an UD QP data in order after moving it to RTS state. ... ok
test_query_raw_qp (tests.test_qp.QPTest)
Queries an RAW Packet QP after creation. Verifies that its properties ... skipped 'To Create RAW QP must be done by root on Ethernet link layer'
test_query_rc_qp (tests.test_qp.QPTest)
Queries an RC QP after creation. Verifies that its properties are as ... ok
test_query_uc_qp (tests.test_qp.QPTest)
Queries an UC QP after creation. Verifies that its properties are as ... ok
test_query_ud_qp (tests.test_qp.QPTest)
Queries an UD QP after creation. Verifies that its properties are as ... ok

----------------------------------------------------------------------
Ran 26 tests in 0.018s

OK (skipped=10)
```
为了方便，也可直接把pyverbs所在的目录export到PYTHONPATH里面：
```bash
export PYTHONPATH=/home/ame/rdma-core/build/python:$PYTHONPATH
```
Pyverbs作为Cython库的原理是：
![](https://cdn.nlark.com/yuque/0/2023/webp/36097650/1685781835209-bbd30347-3764-4639-a3e0-17bac996cd3e.webp#averageHue=%23696969&clientId=uf2d59343-2d9b-4&from=paste&id=ua2ff8907&originHeight=248&originWidth=1568&originalType=url&ratio=1.5&rotation=0&showTitle=false&status=done&style=none&taskId=u0963070b-aaa1-4a9e-a17a-14a47f3012e&title=)
# 内存地址基础知识
# Queue Buffer
# Socket建链
# CM建链

