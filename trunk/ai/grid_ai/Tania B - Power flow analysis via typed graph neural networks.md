

Engineering Applications of Artificial Intelligence 117 (2023) 105567
Contents lists available at ScienceDirect
Engineering Applications of Artificial Intelligence
journal homepage: www.elsevier.com/locate/engappai
Power flow analysis via typed graph neural networks
Tania B. Lopez-Garcia, José A. Domínguez-Navarro
## ∗
University of Zaragoza, C. María de Luna, Zaragoza, 50018, Spain
## A R T I C L E  I N F O
## Keywords:
Power flow
Graph neural networks
Unsupervised learning
Physics-informed neural networks
## A B S T R A C T
Power flow analyses are essential for the correct operation of power grids, however, electricity systems
are becoming increasingly complex to analyze with the conventional numerical methods. The present work
proposes a typed graph neural network based approach to solve the power flow problem. The neural networks
are trained on benchmark power grid cases which are modified by varying the injections (load and generation),
branch characteristics and topology. The solution to the power flow analysis is found when all voltage values
are known. The proposed system infers the voltage magnitude and phase and is trained so that the obtained
values minimize the violation of the physical laws that govern the system, this way the training is achieved in
an unsupervised manner. The proposed solver has linear time complexity and is able to generalize to grids with
considerably different conditions, including size, from the grids available during training. Though the training
is unsupervised and does not suppose any ground truth data, the solutions obtained are found to have a close
correlation with the conventional Newton–Raphson method. The results are additionally validated by finding
the root mean square deviation from the Newton–Raphson method, and the faster, though less accurate, DC
approximation method.
## 1. Introduction
For correct power system operation, power flow analyses must
be executed frequently, as they are necessary for many procedures
such as power systems planning, security assessment, management and
optimization, Glover et al. (2012). Conventionally, the power flow
analysis is carried out by determining and solving a set of non-linear
algebraic equations with iterative numerical analysis methods; most
known methods of this type have been tested at some point to solve
the power flow problem, Stott (1974) and van Amerongen (1989). In
recent years both the importance and complexity of software modeling
of the electrical grid have increased due to higher electrical demand
and the need to increase the sustainability of the conventional power
grid, Smith et al. (2022). These issues arise from the ambitious, yet nec-
essary, goals for emission reduction. Electrification of diverse energy
sectors, such as heating and transport, has become a strategy for decar-
bonization, this phenomenon has consequently increased the demand
and the dependence on electricity, Xie et al. (2021). In parallel, the use
of variable renewable energy sources (VRES), such as solar and wind,
is expanding. VRES are non-dispatchable and require power systems
to become more flexible; they may cause loading in sections of the
grid where it is usually not expected and cause instability, Babatunde
et al. (2020). Many of the methods currently used for power system
modeling were developed before widespread integration of VRES and
the electrification of transport and heating, furthermore, most are
## ∗
Corresponding author.
E-mail addresses:lopez.200916947@gmail.com (T.B. Lopez-Garcia), jadona@unizar.es (J.A. Domínguez-Navarro).
computationally intensive. The increasing complexity of the electricity
system may become too convoluted to describe in a timely and precise
manner with conventional PF analysis approaches, thus requiring the
investigation of new tools for power system modeling (Tovar-Facio
et al., 2021).
With the emergence of artificial intelligence, many systems such
as decision trees, neural networks and fuzzy logic methods have been
applied to power system problems, Vankayala and Rao (1993) and
Lopez-Garcia et al. (2020). Amongst these approaches, artificial neural
networks (NNs) have shown promise to a certain extent, due to their
ability to synthesize complex mappings accurately and rapidly, along
with the possibility to continuously learn. However, most NNs used for
power system modeling, such as in Hu et al. (2021) and Fikri et al.
(2018), implement multi-layer perceptrons (MLPs). MLPs usually suffer
from local minima and over-fitting issues, in addition to not scaling
well to larger power grids; MLP based models cannot be used for grids
of different size or configuration from the ones they are trained on.
Recently, graph neural networks (GNNs) have gained popularity for
learning structured data and transferring learned information beyond
training conditions (Battaglia et al., 2018). These methods convey
strong relational inductive biases by establishing the GNN architecture
directly on the structure of the analyzed system, which guides these
approaches towards learning not only about the elements of the system,
but also the relationships between them. By basing the proposed solver
on GNNs, several advantages are introduced, such as scaling well to
https://doi.org/10.1016/j.engappai.2022.105567
Received 8 June 2022; Received in revised form 11 October 2022; Accepted 25 October 2022
Available online 15 November 2022
0952-1976/©2022 The Author(s). Published by Elsevier Ltd. This is an open access article under the CC BY-NC-ND license
## (http://creativecommons.org/licenses/by-nc-nd/4.0/).

T.B. Lopez-Garcia and J.A. Domínguez-NavarroEngineering Applications of Artificial Intelligence 117 (2023) 105567
larger power grids, and having the ability to generalize decently on
grids of different size and configuration from the grids seen during
training.
There are a few other works that apply GNNs (or NNs in general)
for power grid analysis. The work in Owerko et al. (2020) uses GNNs
but is based on imitation learning, and thus the GNN is burdensome to
train and does not generalize well outside similar cases to those seen in
training. A pioneering work by Donon et al. (2020) also applies GNNs,
and training is carried out in an unsupervised manner, however the
model is complicated and does not consider changes in grid topology
during training.
The proposed model presents a simple GNN based solver to calculate
the AC power flow in a way that allows to solve many different scenar-
ios in parallel, considering the continuously changing balance between
energy supply and demand, and does this in linear time as opposed
to the exponential time needed for conventional methods that solve
Jacobian matrices. The proposed solver is based on a generalization
of GNNs called typed graph networks (TGNs) (Avelar et al., 2019),
which allows different types of elements to be defined instead of the
usual nodes and edges. The use of TGNs allows to obtain more faithful
representations of the different elements present in electrical grids, such
as the branches and the different types of buses, by considering each of
them as different node types in the corresponding graph representation.
Like other GNN based models, the presented solver can generalize to
electrical grids of different sizes and parameters, yet it additionally
considers changes in the grid topology during training, making it
specially adequate for analyzing different scenarios of possible line
outages, which is essential for security assessments. Additionally, the
training is carried out in an unsupervised manner, applying physics-
informed neural networks by incorporating information of the physical
system in the loss function and aiming to minimize the violation of
the physical laws that govern the system, thus eliminating the time
consuming need of solving the training cases beforehand with other
solvers to produce targets. The solver is modular in nature, allowing to
connect different node types in any desired configuration. Additionally
the time complexity of the proposed solver is linear, in contrast with
common methods, such as the Newton–Raphson, which has exponential
time complexity.
In summary, the proposed method consists of a TGN based sys-
tem that abstracts the relationship between the different elements
in the electrical grid to solve the steady state power flow problem
for dynamical networks, i.e. considering different grid configurations,
injections and branch characteristics. Thus, the presented work presents
a valuable step towards developing a machine learning based system
that is able to assist in analyzing flexible electrical grids of increasing
complexity, while improving speed and reducing the computational
burden of essential power flow analyses.
## 2. Preliminaries
In this section the basic components and power flow formulation
are described, along with a general description of TGNs, which are the
basis of the proposed model and solver. The description of the variables
used to describe the electrical grid can be found in Table 1, and the
definition of the main components used in the proposed solver are
found in Table 2.
## 2.1. Powerflowformulation
This work focuses on solving the power flow problem of power
grids in a steady-state condition. Power grids are basically formed by
buses, branches, loads and generators. The buses are the nodes to which
the other elements are connected. Branches connect two buses and are
modeled internally using the standard휋transmission line model. The
branch series impedance is given by the complex value:푧
## 푘
## =푟
## 푘
## +푖푥
## 푘
## ,
where the resistance of the branch model constitutes the real part, and
## Table 1
Power grid nomenclature.
VariableUnitsDefinition
푛–Bus ID index
푚–Generator bus ID index
푘–Branch ID index
from
## 푘
–Sender bus ID of branch푘
to
## 푘
–Receiver bus ID of branch푘
## 푉
## 푛
kVVoltage magnitude at bus푛
## 휃
## 푛
radVoltage phase at bus푛
## 푃푑
## 푛
MWActive power load at bus푛
## 푄푑
## 푛
MVArReactive power load at bus푛
## 푃푔
## 푚
MWActive power generation at generation bus푚
## 푉 푔
## 푚
kVVoltage magnitude setpoint at generation bus푚
## 푟
## 푘
ΩSeries resistance for branch푘
## 푥
## 푘
ΩSeries reactance for branch푘
## 푏
## 푘
푆Total line charging susceptance for branch푘
## 휏
## 푘
–Transformer tap ratio
## 휃
shift
## 푘
radTransformer phase shift
the equivalent reactance, the imaginary part. The shunt susceptance of
the equivalent branch model is represented by푏
## 푘
; this general model
can include an ideal phase shifting transformer located at the sender
end of the branch. The objective of the power flow analysis is to
determine the voltage magnitude and phase at all buses for a given
load, generation, and grid configuration state.
The power that flows through the grid depends on the power
imbalances at the buses and the impedance of the branches, while
the power balance at each bus is determined by the possible loads,
generators and branches attached to it. Loads and generators constitute
the external injections of the power grid, loads as a specified power
demand, and generators as a specified power source. Given the grid
topology, the specified values of the injections and line characteristics,
the proposed power flow solver computes the resulting voltages in
the buses and hence the current flow through the branches can be
determined. The relationship between the branch characteristics, the
voltages of the buses and the currents is given by:
## [
## 푖
from
## 푘
## 푖
to
## 푘
## ]
## =푌
## 푏푟,푘
## [
## 푣
from
## 푘
## 푣
to
## 푘
## ]
## (1)
where푖
from
## 푘
and푖
to
## 푘
represent the complex current injections at the
sender and receiver sides of branch푘, respectively;푣
from
## 푘
and푣
to
## 푘
are
the complex voltage values at the sender and receiver sides of branch
푘, respectively; the푘branch admittance matrix푌
## 푏푟,푘
given by:
## 푌
## 푏푟,푘
## =
## ⎡
## ⎢
## ⎢
## ⎢
## ⎣
## (
## 푦
## 푘
## +푖
## 푏
## 푘
## 2
## )
## 1
## 휏
## 2
## 푘
## −푦
## 푘
## 1
## 휏
## 푘
## 푒
## −푖휃
shift
## 푘
## −푦
## 푘
## 1
## 휏
## 푘
## 푒
## −푖휃
shift
## 푘
## 푦
## 푘
## +푖
## 푏
## 푘
## 2
## ⎤
## ⎥
## ⎥
## ⎥
## ⎦
## (2)
where the series admittance element푦
## 푘
is denoted by푦
## 푘
## =
## 1
## 푧
## 푘
## .
It should be noted that before the load flow is solved, the network
losses are unknown, thus, a generator bus, called the slack bus, is
designated to compensate for these losses. The voltage magnitude and
phase are given beforehand for the chosen slack bus (푛= 0), and
the power needed to compensate for the total grid losses must be
determined. In addition to the slack bus, two other types of buses are
defined:푃푉buses constitute the set of buses directly connected to a
generator (that are not the slack bus); the remaining non-generation
buses are classified as푃푄buses. For each푃푉bus푛
## 푃푉
, the voltage
magnitude is given by푉 푔
## 푛
## 푃푉
and the generated active power is given
by푃푔
## 푛
## 푃푉
; for these buses the voltage phase휃
## 푛
## 푃푉
, and the generated
reactive power푄푔
## 푛
## 푃푉
, must be determined. For each푃푄bus푛
## 푃푄
, the
active and reactive powers are given by:푃
## 푛
## 푃푄
## = −푃푑
## 푛
## 푃푄
and푄
## 푛
## 푃푄
## =
## −푄푑
## 푛
## 푃푄
; for these buses both voltage magnitude and phase,푉
## 푛
## 푃푄
and
## 휃
## 푛
## 푃푄
, must be found.
For a solution to be obtained, the power balance in all nodes must
be achieved by solving a non-linear equation system of the form훥푆= 0,
## 2

T.B. Lopez-Garcia and J.A. Domínguez-NavarroEngineering Applications of Artificial Intelligence 117 (2023) 105567
Fig. 1.Relationship between a power grid toy example and the corresponding TGN layer.
## Table 2
Proposed solver components.
ComponentDefinition
A graph
휁Set of node types
## 
## 푖
Set of type푖nodes
## 푑
## 푖
Embedding dimension of type푖nodes
퐀Adjacency matrix
퐿Total message passing iterations
푇Total TGN layers
which is deconstructed into nodal power balance equations as functions
of unknown voltage values, as shown below for a bus푛:
## 훥푃
## 푛
## (푉
## 푛
## ,휃
## 푛
## ) =푃푔
## 푛
## −푃푑
## 푛
## − Re
## ⎡
## ⎢
## ⎢
## ⎢
## ⎣
## ⎛
## ⎜
## ⎜
## ⎜
## ⎝
## ∑
## 푘∈(푛)
## 푛=from
## 푘
## 푖
from
## 푘
## +
## ∑
## 푘∈(푛)
## 푛=to
## 푘
## 푖
to
## 푘
## ⎞
## ⎟
## ⎟
## ⎟
## ⎠
## ⋅푣
## 푛
## ⎤
## ⎥
## ⎥
## ⎥
## ⎦
## (3)
## 훥푄
## 푛
## (푉
## 푛
## ,휃
## 푛
## ) =푄푔
## 푛
## −푄푑
## 푛
## − Im
## ⎡
## ⎢
## ⎢
## ⎢
## ⎣
## ⎛
## ⎜
## ⎜
## ⎜
## ⎝
## ∑
## 푘∈(푛)
## 푛=from
## 푘
## 푖
from
## 푘
## +
## ∑
## 푘∈(푛)
## 푛=to
## 푘
## 푖
to
## 푘
## ⎞
## ⎟
## ⎟
## ⎟
## ⎠
## ⋅푣
## 푛
## ⎤
## ⎥
## ⎥
## ⎥
## ⎦
## (4)
where푘∈(푛)represents all the branches that are connected to bus
## 푛.
There are푁
## 푝푣
## + 2푁
## 푝푞
voltage values that must be found (only
phase for푃푉buses and both phase and magnitude for푃푄buses),
where푁
## 푝푣
and푁
## 푝푞
are the number of푃푉and푃푄buses, respectively.
## Afterwards,푁
## 푝푣
+ 1reactive power balance equations are solved to
find the generator reactive power injections, and this way all unknown
variables are found.
## 2.2. Typedgraphnetworks
It results straightforward to represent a power grid as a graph, the
approach taken in this work is illustrated with a toy example in Fig. 1.
The toy power grid shown in Fig. 1(a) includes푃푉,푃푄and slack
nodes, the branches that connect them and the external injections;
Fig. 1(b) shows how the proposed solver architecture is directly related
to the grid structure. The goal of the presented system is to infer the
voltage values by representing the power grid as graph structured data
and learning the relationships between the different elements; in other
words, the proposed system takes a relational data graph as input,
and outputs nodal voltage predictions. To achieve said goal, TGNs are
employed; a brief description is found below.
Normally, a graph is defined as=
## (
## ,
## )
, with= {1,...,푁}a
finite set of nodes, and= {1,...,퐾}⊆×a set of edges defined
as nodal pairs. In a single sample of a graph signal, an input vector
## 푥
## 푛
from the graph input퐱∈R
## 푁
is assigned to each node in. The
graph structure, or topology of the graph, is represented in matrix form,
typically by an adjacency matrix퐀∈R
## 푁×푁
, defined as:
## 퐴
## 푖,푗
## =
## {
## 1,if(푖,푗) ∈
## 0otherwise
## (5)
The generally accepted graph network model proposed by Battaglia
et al. (2018) projects the nodes, edges, and possibly the entire graph to
a푑-dimensional space. The nodal embedded states iteratively add infor-
mation from their푘-hop neighborhood over numerous message-passing
steps, in which nodes are updated as a function of the embedded values
of neighboring nodes and their own previous state. Information is
propagated between nodes, edges and possibly the whole graph (Gilmer
et al., 2017). The broadcasting of signals on the graph is computed
as a series of local operations, commonly matrix multiplications with
adjacency matrices are employed. Taking푧
## (푙)
## 푛
## ∈R
## 푑
as the embedded
state of node푛on iteration푙, the embedding, updating and outputting
steps are:
## 퐳
## (0)
## =퐱(6)
## 퐳
## (푙+1)
## =푓
## (
## 퐳
## (푙)
## ,
## ̄
## 퐀
## )
## (7)
## 퐳
## (퐿)
## =퐲(8)
where퐳represents the embedded state of the graph,퐲the nodal
prediction output,푓a non-linear state update function that depends
on the accumulated messages of neighboring nodes and the previous
state of the nodes themselves;
## ̄
퐀=퐀+, withas the identity
matrix, is an adjacency matrix augmented with self loops (to allow the
incorporation of information from the nodes themselves, and not just
from neighboring nodes) (Kipf and Welling, 2017).
The elements of the power grid are related through the grid topol-
ogy, and the state of the grid depends on both external injections and
this configuration, it is thus evident that a natural correspondence
between power grids and graph networks exists. However, the defined
bus types are fundamentally different in that each has different char-
acteristics and a different number of expected outputs. Furthermore,
the branch characteristics are important factors in determining the
resulting voltages, such that they cannot be treated as simple edges,
but are not expected to produce an output. In essence, the different grid
elements should be treated as distinct node types, as shown in Fig. 1(b).
TGNs are a generalization of GNNs, in that instead of defining
nodes and edges as the graph elements, the concept of node types is
adopted. This way the edges can be defined as a type of node, and a
finite number of additional node types can be designated. This outlook
presents several advantages; each node type can have different output,
projected state dimensions, and update function parameters.
This way a relevant difference with respect to conventional GNNs is
the way the message-passing and update iterations are computed. For a
TGN with a휁set of node types, message passing functions are defined
## 3

T.B. Lopez-Garcia and J.A. Domínguez-NavarroEngineering Applications of Artificial Intelligence 117 (2023) 105567
for node types that have at least one pair of adjacent nodes, to compute
messages from one projection dimension to the other:
## = {휇∶R
## 푑
## 푗
## →R
## 푑
## 푖
## |푖,푗∈휁, 퐴
## 푖,푗
## ≠ퟎ}(9)
The outputs from the message passing functions are propagated via
matrix multiplication with adjacency matrices that indicate the sparsity
pattern between the different node types, e.g. an adjacency matrix
between types푖and푗nodes is represented as퐴
## 푖,푗
## ∈R
## 푑
## 푖
## ×푑
## 푗
. For each
node type푖, their corresponding update function,휙
## 푖
concatenates their
previous state with the propagated messages from neighboring node
types, such that:
## 휙
## 푖
## ∶R
## 푑
## 푖
## +퐷
## 푖
## →R
## 푑
## 푖
## (10)
## 퐷
## 푖
## =
## ∑
## 휇∶R
## 푑
## 푗
## →R
## 푑
## 푖
## 푗∈(푖)
## 푑
## 푖
## (11)
where(푖)represents the set of all node types that directly interact
with type푖nodes, and퐷
## 푖
is the dimension of the final accumulation
of messages that are concatenated from the neighboring node types.
Thus the update function input for each node consists of the final
accumulation of messages concatenated with their previous node state.
This way, the TGN structure takes as input a feature vector for every
node of every node type, i.e.퐱
## 푖
## ∈R
## 푓
## 푖
, for a node type푖, where푓
## 푖
is
the dimension of the input features. All nodes are projected to their
corresponding embedding space through a linear function,훾
## 푖
## ∶퐱
## 푖
## →
## 퐳
## 푖
## ∈R
## 푑
## 푖
. Then message passing and node update functions are repeated
iteratively for퐿message passing steps. The nodal outputs are obtained
from a final mapping,휑
## 푖
## ∶퐳
## 푖
## →퐲
## 푖
## ∈R
## 표
## 푖
; where표
## 푖
is the desired output
dimension for푖type nodes.
## 3. Methodology
In this section a description of how the TGN framework is applied
to solve the power flow problem is presented. It is shown that by
training four small MLPs, the power flow problem can be solved in
linear time, robust to changes in topology (in particular to single
branch line outages) and different branch characteristics. The training
is not supervised, but physics-informed, and the solver architecture is
modular in nature. First a description of the proposed TGN based model
is reported, and then the training mechanism is explained.
3.1. TGNbasedpowerflowsolver
In the proposed method, a predefined number푇of TGN layers is
used to iteratively approximate the missing voltage values at every
node of the power grid. The message passing and update functions,휇
and휙, are small fully connected neural networks; their parameters are
the only ones that must be learned. These functions are the same for
all nodes of the same type in the same layer, supporting the concept of
combinatorial generalization, this way, the same TGN architecture can
operate with input graphs of different sizes and shapes.
While the embedding, message passing, update and output functions
of each TGN layer are independently parameterized, the layers are
structurally the same; each one is defined by four types of nodes:
branch nodes (
## 퐸
) to include branch characteristics,푃푉nodes (
## 푃푉
## )
for generator buses,푃푄nodes (
## 푃푄
) for load buses, and slack nodes
## (
## 푆
) for slack buses. Different input features are defined for each type
of node, as shown below for a layer푡:
## 퐱
## 푃푉
## ⎧
## ⎪
## ⎪
## ⎨
## ⎪
## ⎪
## ⎩
## 푉
## 푖
## (푡)
## 휃
## 푖
## (푡)
## 훥푃
## 푖
## (푡)
## 푄푔
## 푖
## (푡),
## 퐱
## 푃푄
## ⎧
## ⎪
## ⎪
## ⎨
## ⎪
## ⎪
## ⎩
## 푉
## 푗
## (푡)
## 휃
## 푗
## (푡)
## 훥푃
## 푗
## (푡)
## 훥푄
## 푗
## (푡),
## 퐱
## 푆
## ⎧
## ⎪
## ⎪
## ⎨
## ⎪
## ⎪
## ⎩
## 푉
## 푠
## 휃
## 푠
## 푃푔
## 푠
## (푡)
## 푄푔
## 푠
## (푡),
## 퐱
## 퐸
## ⎧
## ⎪
## ⎨
## ⎪
## ⎩
## 휌(푟
## 푘
## ,푥
## 푘
## )
## 훿(푟
## 푘
## ,푥
## 푘
## )
## 푏
## 푘
## (12)
## ∀푖∈
## 푃푉
## ,∀푗∈
## 푃푄
## ,∀푠∈
## 푆
## ,∀푘∈
## 퐸
As was mentioned in Section 2.1, the branch series impedance is
given by the complex value:푧
## 푘
## =푟
## 푘
## +푖푥
## 푘
## =
## |
## |
## 푧
## 푘
## |
## |
∠휑, however, making
reference to the conventional admittance matrix, the branches admit-
tance magnitude and phase are chosen as features. The admittance is
given by:푦
## 푘
## =
## 1
## 푧
## 푘
## =
## 1
## |
## 푧
## 푘
## |
∠−휑=휌∠훿. Defining the magnitude and phase
of the series admittance of each branch as휌and훿, respectively, the first
two branch node features are thus established as:
## 휌(푟
## 푘
## ,푥
## 푘
## ) =
## 1
## √
## 푟
## 2
## 푘
## +푥
## 2
## 푘
## (13)
## 훿(푟
## 푘
## ,푥
## 푘
## ) = −arctan(
## 푥
## 푘
## 푟
## 푘
## )(14)
The last branch node feature푏
## 푘
corresponds to the total line
charging susceptance. These branch input features remain unchanged
throughout all TGN layers. Concerning the other features, the rotating
angle of the buses is measured relative to the chosen slack bus, as
is common in power flow analyses, i.e.휃
## 푛
## =휃
## 푠
## ,∀푛∈
## (
## 
## 푃푉
## ⋃
## 
## 푃푄
## )
## .
Apart from this, an initial ‘flat’ guess of voltage magnitude values is
established, with푉
## 푗
= 1(per unit),∀푗∈
## 푃푄
. This initial voltage state
is used for the first TGN layer, and the following TGN layers receive the
voltage approximation of the previous layer; after each approximation,
the power balance error (훥푃and훥푄) is calculated at each bus and is
used as part of the input features for the next TGN layer. The reactive
power at generator buses is locally compensated, such that훥푄
## 푗
## = 0,
this does not provide additional information and is thus excluded from
the
## 푃푉
input features. A similar situation happens with the slack
node where both active and reactive powers are compensated; thus, the
calculated powers generations are used as input features. Furthermore,
the same adjacency matrices are used for every layer of the TGN based
solver since the configuration of the power grid is not altered between
layers.
For the message-passing steps three distinct adjacency matrices are
defined: between
## 퐸
nodes and
## 푃푉
## ,
## 푃푄
and
## 푆
nodes, as shown
in Eq. (15). Only three adjacency matrices are needed because bus
type nodes cannot be directly connected to each other, but instead are
always connected through branch type nodes. The adjacency matrices
may be transposed depending on whether information is moving from
a branch node to a bus node, or vice versa.
## 퐀
## 푃푉 , 퐸
## ∈R
## |
## 푃푉
## |×|
## 퐸
## |
## 퐀
## 푃푄, 퐸
## ∈R
## |
## 푃푄
## |×|
## 퐸
## |
## (15)
## 퐀
## 푆, 퐸
## ∈R
## 1×|
## 퐸
## |
A predefined number퐿of message passing and state update steps
is set; for this procedure, the same NNs휇and휙, are applied at each
iteration to propagate and aggregate information across the graph,
and update the graph state. At the final update step, each node has
shared information with neighboring nodes퐿−hops away (Battaglia
et al., 2018). This iterative message-passing and updating process is
illustrated in Fig. 2. The output of each TGN layer is obtained by
decoding the final states of the
## 푃푉
and
## 푃푄
node types. The layer
outputs correspond to the inferred change in voltage values,훥푉and
훥휃, with respect to the input voltage values, for the corresponding TGN
layer, as shown below:
## 퐲
## 푃푉
## {
## 훥휃
## 푖
## ,퐲
## 푃푄
## {
## 훥푉
## 푗
## 훥휃
## 푗
## ,(16)
## ∀푖∈
## 푃푉
## ,∀푗∈
## 푃푄
The voltage values after every TGN layer are updated by:
## ̂
## 푉(푡+ 1) =훥푉+
## ̂
## 푉(푡)(17)
## ̂
## 휃(푡+ 1) =훥휃+
## ̂
## 휃(푡)(18)
With the updated voltage values, Eqs. (3) and (4) are used to
calculate the power balance error in each bus, the reactive power
## 4

T.B. Lopez-Garcia and J.A. Domínguez-NavarroEngineering Applications of Artificial Intelligence 117 (2023) 105567
Fig. 2.Message passing and update state procedure (shared weights).
compensation in generator buses, and both active and reactive power
compensation in the slack bus. If the last layer has not been reached, the
voltage values and power balance error values are used to determine
the graph input for the next TGN layer, otherwise, they are used to
evaluate the cost function. The iterative portion of the proposed power
solver structure is summarized by Algorithm 1 and illustrated in Fig. 3.
If the model is being trained, the final voltage inference is used with the
power equilibrium equations to calculate the loss function and then the
Adam optimization algorithm is applied to find new NN parameters, as
is explained in Section 3.3. If the model is not being trained, the process
ends with the final voltage inference values.
Algorithm1TGN based PF solver
## Require:=
## ⋃
## 푖∈휁
## 
## 푖
## ,퐴
## 푖,푗
## ∈R
## 푑
## 푖
## ×푑
## 푗
## |푖,푗∈휁,휁= {푃푉 ,푃푄,푆,퐸}
Input:=grid state (injections, branch characteristics,
topology)
## 1:
## ̂
## 푉
## (0)
## 푃푄
## = 1,
## ̂
## 휃
## (0)
## 푃푉 ,푃푄
= 0⊳Flat start
## 2:푡= 0
3:while푡≤푇do⊳Iterate over a predefined number of TGN layers
## 4:훥푃
## (푡)
## =푃
## 푔
## −푃
## 푑
## −푃
## 푏푢푠
## (
## ̂
## 푉
## (푡)
## ,
## ̂
## 휃
## (푡)
)⊳Power balance error
## 5:훥푄
## (푡)
## =푄
## 푔
## −푄
## 푑
## −푄
## 푏푢푠
## (
## ̂
## 푉
## (푡)
## ,
## ̂
## 휃
## (푡)
## )
6:foreach푖∈휁do⊳For all node types
## 7:퐱
## 푖
## =퐟
## 푖
## (
## ̂
## 푉
## (푡)
## ,
## ̂
## 휃
## (푡)
## ,훥푃
## (푡)
## ,훥푄
## (푡)
,)⊳Input features:퐱
## 푖
## ∈R
## 푁
## 푖
## ×푓
## 푖
## 8:퐳
## (0)
## 푖
## =훾
## 푖
## (퐱
## 푖
)⊳Node embedding:퐳
## 푖
## ∈R
## 푁
## 푖
## ×푑
## 푖
## 9:푙= 0
10:while푙≤퐿do⊳ 퐿message-passing steps
## 11:̄휇
## 푖
## =concat
## (
## 퐴
## 푖,푗
## ⋅휇
## 푖
## (
## 퐳
## (푙)
## 푗
## ))
,∀푗∈(푖)⊳Message
aggregation
## 12:퐳
## (푙+1)
## 푖
## =휙
## 푖
## (
## 퐳
## (푙)
## 푖
## , ̄휇
## 푖
## )
⊳Update∀푖≠푆
## 13:푙←푙+ 1
## 14:endwhile
## 15:endfor
## 16:
## ̂
## 푉
## (푡)
## 푃푉
## =휑
## 푃푉
## (
## 퐳
## (퐿)
## 푃푉
## )
⊳Outputs:퐲
## 푖
## ∈R
## 푁
## 푖
## ×표
## 푖
## 17:
## ̂
## 푉
## (푡)
## 푃푄
## ,
## ̂
## 휃
## (푡)
## 푃푄
## =휑
## 푃푄
## (
## 퐳
## (퐿)
## 푃푄
## )
## 푡←푡+ 1
## 18:endwhile
## Output:
## ̂
## 휃
## (푇)
## 푃푉
## ,
## ̂
## 푉
## (푇)
## 푃푄
## ,
## ̂
## 휃
## (푇)
## 푃푄
⊳Final voltage inference
## 3.2. Modelcomputationalcomplexity
Each TGN layer is composed of four main functions: encoding,
message passing, updating and decoding. The four functions are defined
by small MLPs, with either one or two layers. All MLPs with two layers
have one layer with a hyperbolic tangent activation function, and a
linear layer; the MLPs with a single layer are linear. Different instances
of the encoding MLPs are defined for each of the four node types (
## 푃푉
## ,
## 
## 푃푄
## ,
## 퐸
## ,
## 푆
); these MLPs have a single layer of size푓
## 푥
## ×푑
## 푥
for each
node type푥, where푓
## 푥
and푑
## 푥
are the corresponding feature vector size
and embedding dimension, respectively. Five message passing functions
are defined: two to exchange information to and from
## 푃푉
and
## 퐸
## ,
two to exchange information between
## 푃푄
and
## 퐸
, and one for passing
information from
## 푆
to adjacent
## 퐸
nodes. The message passing MLPs
have two layers, the first of size푑
## 퐼푁
## ×푑
## 퐼푁
, and the second of size
## 푑
## 퐼푁
## ×푑
## 푂푈푇
. When a type푥node casts information unto a type푦node
## (
## 푥
## →
## 푦
## ),푑
## 퐼푁
and푑
## 푂푈푇
represent the embedding size of the type푥
and type푦nodes, respectively. Only
## 푃푉
## ,
## 푃푄
and
## 퐸
are updated;
## 푆
nodes pass their corresponding information through the
## 퐸
nodes but
do not need to be updated, as no information is sent to them and no
output is required from them.
## 퐸
nodes receive information from
## 푆
## ,
## 
## 푃푉
and
## 푃푄
## ;
## 푃푉
and
## 푃푄
nodes only receive information from
## 퐸
## .
The aggregating and update function for
## 퐸
has two layers, one of size
## (푑
## 퐸
## +푑
## 푃푉
## +푑
## 푃푄
## +푑
## 푆
## ) ×푑
## 퐸
, and the other of size푑
## 퐸
## ×푑
## 퐸
. The update
functions for generator and load bus type nodes also have two layers,
one of size(푑
## 푥
## +푑
## 퐸
## )×푑
## 푥
, and the other of size:푑
## 푥
## ×푑
## 푥
, where푥=푃푉
or푥=푃푄. Only
## 푃푉
and
## 푃푄
require an output, their decode MLPs
consist of a single layer of size푑
## 푥
## ×표
## 푥
, where표
## 푃푉
## = 1and표
## 푃푄
## = 2. In
total, each TGN layer has the following number of trainable parameters
## 푃:
## 푃= (4푑
## 푃푉
## + 4푑
## 푃푄
## + 4푑
## 퐸
## + 2푑
## 푆
## )푑
## 퐸
## + 3푑
## 2
## 푃푉
## + 3푑
## 2
## 푃푄
## +푑
## 2
## 푆
## +(퐹
## 푃푉
## +퐺
## 푃푉
## )푑
## 푃푉
## + (퐹
## 푃푄
## +퐺
## 푃푄
## )푑
## 푃푄
## +퐹
## 퐸
## 푑
## 퐸
## +퐹
## 푆
## 푑
## 푆
## (19)
If all embedding dimensions are the same푑value, then:
## 푃= 21푑
## 2
## + (퐹
## 푃푉
## +퐺
## 푃푉
## )푑+ (퐹
## 푃푄
## +퐺
## 푃푄
## )푑+퐹
## 퐸
## 푑+퐹
## 푆
## 푑(20)
In this particular case, for simplicity, all nodes were embedded to
the same dimension, with푑= 16, so that푃= 5648. This value is
independent of the size of the electrical grid.
## With푁
## 푥
representing the cardinality of a type푥node set, the encod-
ing function for a type푥node has complexity(푓
## 푥
## 푁
## 푥
## 푑
## 푥
), and since푓
## 푥
and푑
## 푥
are predefined constants, this translates to a(푁
## 푥
## )complexity.
Similarly, each decoding and message passing function has complexity
## (푁
## 푥
). The update function includes an aggregation procedure which
involves the multiplication of sparse adjacency matrices, with dense
matrices that represent messages passed from one type of node to
another. The total amount of values in all sparse matrices is2푁
## 퐸
, the
complexity of the aggregation multiplications for a type푥node is at
most(2푁
## 퐸
## 푑
## 푥
). The total amount of nodes푁=푁
## 푃푉
## +푁
## 푃푄
## +푁
## 푆
## +푁
## 퐸
depends on the particular case of electrical grid, but as all operations
have at most(퐷푁) =(푁)complexity (with퐷being some constant
dependent on the chosen hyperparameters), the time complexity of the
proposed solver is linear with respect to the size of the electrical grid.
## 3.3. Modeltraining
The proposed TGN solver is trained in batches, the independent NNs
of the TGN layers are trained simultaneously based on a cost function
that only considers the final voltage inference and the resulting power
balance error. The cost function is given by:
## 1
## 퐻
## 퐻
## ∑
## ℎ=1
## (
## 1
## 푁
## 푁
## ∑
## 푛=1
## (
## 훥푃
## 2
## 푛,ℎ
## +훥푄
## 2
## 푛,ℎ
## )
## )
## (21)
where푁represents the total number of buses, and퐻the total number
of samples (푛andℎbeing the node and sample indices, respectively).
The gradients of this cost function with respect to the parameters of the
## 5

T.B. Lopez-Garcia and J.A. Domínguez-NavarroEngineering Applications of Artificial Intelligence 117 (2023) 105567
Fig. 3.TGN based power solver structure.
embedding, message-passing, update and output NNs is calculated with
the backpropagation algorithm. These gradients are used to modify the
values of the NN parameters via the Adam optimization algorithm,
afterwards a new batch of data is introduced to the TGN model and
the process is repeated until the cost function converges to a minimum
value. This way, as is evident, the learning is unsupervised; the goal of
the cost function is to enforce Kirchhoff’s current law by minimizing
the power balance error in all nodes.
## 4. Numericaltestsanddiscussion
In this section the design of the experiments performed to validate
the proposed TGN based power flow solver is described, along with the
results obtained.
## 4.1. Dataset
The data for all experiments is based on benchmark IEEE test
cases, similar to the default test cases available for Matpower (Zim-
merman et al., 2011); perturbations are added to the injections, branch
characteristics and grid topology for each sample.
The information of the IEEE test cases is imported through three
two dimensional arrays, with information for the buses, generators,
and branches, respectively. From the bus array, the values of the
active and reactive power demand are extracted, and a proper ID
number is assigned to each substation. Uniform noise is added to the
value of the active and reactive power loads,푃푑and푄푑, so that the
resulting values vary between 50% and 150% of the original value. The
power load is restricted so that the rare case of the total load demand
being higher than the sum of the maximum power generation limits
is avoided. From the branch array, the indices of the buses at each
side of the branch is collected, as well as the resistance, reactance,
susceptance and tap ratio values of the branch. Similarly as with the
bus perturbations, uniform noise is added to these values so that they
are between 90% and 110% of the test case value. An important aspect
of the presented work is the introduction of change to the electrical grid
topology in the different samples during training of the system; to this
effect, in each sample a different random branch is disconnected. This
way both injection and topology changes are involved during training.
From the generator array, the ID of the generator bus is considered,
along with the maximum permitted active power generation and the
nominal voltage magnitude of these buses. The voltage magnitude is
uniformly sampled between 90% and 110% of the nominal value, the
active power generation is uniformly sampled between 25% and 75%
of the allowed range. All voltage magnitude values from load buses are
initialized to1P.U. and all voltage phase values are set to the slack bus
angle reference.
## 6

T.B. Lopez-Garcia and J.A. Domínguez-NavarroEngineering Applications of Artificial Intelligence 117 (2023) 105567
This way, a group of objects that represent a batch of electrical grid
samples is formed. Said representation is structured so that it is ready to
be used to calculate adjacency matrices and the inputs to the proposed
TGN based model.
## 4.2. Modelconstruction
In the following tests, three electrical grid sizes are employed based
on the case 30, case 57 and case 118 standard IEEE power grids. For
this reason, three instances of the proposed solver are generated, each
trained on an electrical grid of fixed size. The three instances of the
TGN based power solver share the same hyperparameters: number of
TGN layers, number of message passing and update steps, embedded
dimension of node types, and learning rate. The number of TGN lay-
ers is empirically chosen to produce a precise enough solution while
maintaining the overall size of the solver relatively small; this number
is set at푇= 15. Furthermore, to avoid the distortion of messages being
propagated from distant nodes (Topping et al., 2022), only two message
passing and update steps are defined (퐿= 2) for each TGN layer. As
once mentioned previously, the embedded dimension for all types of
nodes is set to푑= 16. The optimizer used is the Tensorflow (Abadi
et al., 2015) implementation of the Adam algorithm, with a learning
rate of1푒−4, and all other parameters are left with the default values.
The three instances are trained relatively quickly, with only1250,1500
and1500learning iterations for the TGN instances trained on case 30,
case 57 and case 118 grids, respectively.
## 4.3. Conventionaltest
The first experiment consists of testing the three instances of the
proposed solver on electrical grids of the same size as the ones they are
trained on, changing power grid injections and disconnecting random
branches. For each grid size, 20 power grid states are generated; the
corresponding TGN instance is applied to infer the missing voltage
values at each node. To validate the obtained results, they are com-
pared with the solutions calculated with the trusted and conventional
Newton–Raphson (N–R) method using Matpower (Zimmerman et al.,
2011). Because of the way the batch samples are generated, some input
samples result in non-feasible grid states that do not converge with
the N–R method, for these cases the proposed solver does infer some
solution, but in the presented results only those that converged with
the N–R method are considered.
To further explain the inference procedure, Fig. 4 shows the ab-
solute difference between the final N–R based result and the outputs
obtained at distinct TGN iterations of the proposed method, for a single
sample of the case 118 grid. This way,푖푡푒푟0corresponds to the output
of the first TGN layer;푖푡푒푟 푡represents an intermediate layer, in this case
푡= 7;푖푡푒푟 푇represents the final output, with푇= 15. The abundance of
low error vertices on the magnitude side of the first layer is due to the
quantity of generator (푃푉) nodes, for which the voltage magnitude is
known from the original state of the grid. As the iterations advance, it
is shown that the output of each node approaches the N–R output, even
though the learning is not supervised and the N–R result is not known
during training.
To exemplify the similarity between the resulting voltage values
obtained with the N–R method and the proposed TGN based solver
Figs. 5 to 7 illustrate the final voltage magnitude and phase results
of a single sample, obtained with the proposed TGN based solver and
the N–R method. Fig. 5 shows the results for a sample state of case 30
grids, displaying the voltage magnitude and phase of each substation
on the left and right graphs, respectively. Figs. 6 and 7 show similar
experiments for case 57 and case 118 grids, respectively. These are
purely illustrative graphs, since they only show the outputs of a single
power grid instance.
In order to show a more general perspective of the precision of
the proposed solver, Figs. 8 to 10 show scatter plots with the N–R
## Table 3
Voltage magnitude RMSE.
Test size
Case 30Case 57Case 118
## DC0.0401390.0456670.028195
TGN Trained on case 302.5092e−043.9902e−031.7344e−03
TGN Trained on case 578.5203e−032.3706e−032.0319e−03
TGN Trained on case 1183.6260e−043.9346e−032.3699e−04
## Table 4
Voltage phase RMSE.
Test size
Case 30Case 57Case 118
## DC0.0129740.0162470.079729
TGN Trained on case 302.2852e−030.0688660.017480
TGN Trained on case 570.012294.4389e−03   1.2320e−03
TGN Trained on case 1186.1418e−030.016860.010423
based solutions and the proposed solver solutions, for test batches with
20samples. The value of the correlation coefficient between the two
results is also shown in the bottom right of the scatter plots. Fig. 8
shows the correlation between the proposed solver solution and the
N–R based solution, for magnitude (PU) on the left and for phase on
the right (radians). That is, the N–R based solutions, for all the buses
in all the samples of the test batch, are compared to the corresponding
values obtained with the proposed method. Figs. 9 and 10 show similar
plots for case 57 and case 118, respectively. In all cases, there is a
high level of correlation with all coefficients being above 0.98; the least
correlated case is the one corresponding to the voltage phase solution of
the case 118 grids. The most correlated case corresponds to the voltage
magnitude solution of the case 118 grids, although this can be partly
explained by the high rate of generator nodes in that specific case (the
voltage magnitude values are known beforehand).
## 4.4. Extrapolationtodifferentgridsizes
One of the crucial points of the proposed model is the capability to
be tested on grids of different size from the ones they are trained on,
due to the graph structure representation of the system. To evaluate
the generalization performance of the proposed solver when faced with
different grid sizes, each of the three TGN instances is tested on batches
of the other two grid sizes that do not correspond to the ones they
were trained on. Each grid in the test batch is obtained as described
in Section 4.3, with varying injections, line characteristics and grid
configuration through the elimination of a random branch.
To add another point of comparison to the results, the test samples
are additionally solved using the DC approximation method, which
does not consider the reactive power in the electrical grid and uses
linear network equations that relate real power to bus voltage angles
(instead of complex bus voltages). The DC approximation is simple
and robust, and for these reasons, sometimes used for contingency or
real-time dispatch analyses (Van Hertern et al., 2006).
In Tables 3 and 4, the solutions obtained with the proposed method
and the DC approximation are compared to the results obtained with
the N–R method, which is considered the correct solution. The compar-
ison is measured using the root mean square error (RMSE):
## 푅푀푆퐸=
## √
## √
## √
## √
## ∑
## 퐻
## 푖=1
## (
## ∑
## 푁
## 푗=1
## (푥
## 푖,푗
## −̂푥
## 푖,푗
## )
## 2
## )
## 푁퐻
## (22)
where푥
## 푖,푗
represents the solution obtained with the newton raphson
method for a bus푗at test sample푖,̂푥
## 푖,푗
represents the corresponding
solution obtained with either the DC approximation method or the
proposed TGN based method,푁represents the total number of buses
of the tested grid and퐻represents the total number of samples in the
test batch.
## 7

T.B. Lopez-Garcia and J.A. Domínguez-NavarroEngineering Applications of Artificial Intelligence 117 (2023) 105567
Fig. 4.Evolution of the absolute difference between the proposed method outputs throughout the TGN layers and the final N–R based output, for a single sample of the case 118
grid, showing voltage phase difference in radians (left) and voltage magnitude in P.U. (right).
Fig. 5.Voltage magnitude and phase solutions for a single sample of the case 30 grid.
Fig. 6.Voltage magnitude and phase solutions for a single sample of the case 57 grid.
## 8

T.B. Lopez-Garcia and J.A. Domínguez-NavarroEngineering Applications of Artificial Intelligence 117 (2023) 105567
Fig. 7.Voltage magnitude and phase solutions for a single sample of the case 118 grid.
Fig. 8.Correlation of TGN based power solver with Matpower’s Newton Raphson solution for case 30 V magnitude (left) and phase (right).
Fig. 9.Correlation of TGN based power solver with Matpower’s Newton Raphson solution for case 57 V magnitude (left) and phase (right).
Fig. 10.Correlation of TGN based power solver with Matpower’s Newton Raphson solution for case 118 V magnitude (left) and phase (right).
The first row of Table 3 shows the voltage magnitude RMSE of the
DC approximation results and the N–R method results, tested on grids
from the three different test case sizes. The following rows show the
RMSE of the solutions obtained with different instances of the proposed
method, trained on case 30, case 57 and case 118 power grids, and
each of them tested on all grid sizes. Table 4 is similar, but comparing
voltage phase values.
The best results for each test case are marked in bold; as would be
expected, most of the best results are obtained from grids tested on
grids of the same size as the ones they were trained on. The results of
the TGN instances tested on grids of the same size as the ones they are
trained on are the same as in Section 4.3. As shown in Table 3, even
when tested on grids of different size, the proposed method performs
better than the DC approximation method when calculating voltage
magnitude, this is expected as the DC approximation method considers
all voltage magnitudes constant at 1 PU. Table 4 shows that in most
cases, the proposed TGN based method performs better than the DC
approximation when calculating voltage phase as well. At times the
## 9

T.B. Lopez-Garcia and J.A. Domínguez-NavarroEngineering Applications of Artificial Intelligence 117 (2023) 105567
Fig. 11.Time in seconds needed to solve different numbers of power grid scenarios,
for the case of 118 buses, using the TGN based solver and the N–R based Matpower
approach.
results are very similar, like with the TGN instance trained on case
57 and tested on case 30 grids, and with the TGN instance trained
on case 118 but tested on case 57 grids. In the worst case, which is
with the TGN trained on case 30 but tested on case 57 grids, the DC
approximation obtained a smaller error, however the TGN solution is
still quite decent. As shown, the worst results are obtained when testing
the case 57 grid, this can be explained by the wide range of values
the injection parameters can take for this particular grid case, which
presents values very different from the ones seen in the other two cases.
Still, the errors in the worse case are considerably small, and it is shown
that smaller grids are able to generalize to bigger grids, and vice versa.
## 4.5. Timeconsiderations
As was mentioned in Section 3.2, the time complexity of the model
is linear, and thus the calculation time does not increase as sharply
as the N–R method with respect to the size of the electrical grid. To
illustrate this, Fig. 11 shows the time in seconds needed to run a
different number of scenarios of the 118 bus test case power grid. The
number of power flow iterations is shown on a logarithmic scale. In
this case, running푛scenarios multiplies the number of inputs by푛
for the proposed solver, and the scenarios are solved in parallel. With
the N–R based approach, the푛scenarios are processed sequentially. It
is shown that although for a small number of inputs the N–R based
method is faster, as the number of inputs grows, the time required is
substantially shorter with the proposed method. These considerations
show an important reduction in the time needed to carry out numerous
power flow iterations, which in combination with the robustness to
single branch outages and differences in branch characteristics, make
it a beneficial tool for power grid planning and risk assessment.
## 5. Conclusion
The proposed TGN based power flow solver takes advantage of
the intuitive connection between the electrical grid data and graph
representations to learn the relationships and dynamics between the
different types of elements present in electrical grid models to ana-
lyze power flow. An important aspect of the presented work is the
generalization capability to infer decent results for essentially different
grids (varying injection, branch characteristics and topology). As far as
the authors know, there is no other work that solves the power flow
problem by training neural networks with both different injections and
different grid configurations. The proposed method does not imitate
any other existing method, but rather is based on minimizing the active
and reactive power imbalance at each node of each sample during the
training of the parameters.
The proposed method exploits several benefits of GNNs, e.g. they
scale linearly with the number of edges and embedding size. Further-
more, since the voltage variables are not directly modified by the
proposed method, we completely avoid the computation of Jacobian
matrices and their inverse, which is necessary in the N–R method.
These two characteristics are key reasons as to why the proposed model
computation time scales in a more linear way with respect to the test
grid size than the N–R method. It is worth mentioning that the testing
of different grid sizes is not possible for conventional MLP methods, and
that these methods are inefficient for larger grids as their size depends
on the grid size, whereas the presented method does not, due to it being
based on local operations and shared modules.
Through the shown numerical tests, it is shown that the proposed
TGN based method obtains results very close to those obtained with a
conventional Newton–Raphson based method, even when the learning
is unsupervised. The tests are carried out in batches, with each sample
of the batch representing an independent electrical grid from the rest.
However, in future work, steps can be taken to capture sequentiality in
time, i.e. instead of the samples being autonomous from each other, if
each sample represents the state of the grid over a certain time duration
훥푡, then퐻samples would represent the grid state evolution over a
total time of퐻⋅훥푡(assuming reliable injection forecast information
is available). Additionally, the framework of the proposed model can
be improved to continuously learn and adapt to the environment.
The results presented constitute a beneficial step toward a NN based
system that can be applied for contingency analysis, real-time dis-
patch and techno-economic analyses, or as an aid to improve different
stages of power system planning, optimization, operation and control
of electrical grids.
CRediTauthorshipcontributionstatement
TaniaB.Lopez-Garcia:Methodology, Software, Writing – original
draft.José A. Domínguez-Navarro:Conceptualization, Supervision,
Critical revision.
## Declarationofcompetinginterest
The authors declare that they have no known competing finan-
cial interests or personal relationships that could have appeared to
influence the work reported in this paper.
## Dataavailability
Data will be made available on request.
## Acknowledgments
This paper was supported in part by the National Council of Science
and Technology (CONACYT), Mexico, under scholarship 710033.
This paper was supported in part by the Spanish National Plan
for Scientific and Technical Research and Innovation, under project
## PID2019-104711RB-I00.
## References
Abadi, M., Agarwal, A., Barham, P., Brevdo, E., Chen, Z., Citro, C., Corrado, G.S.,
Davis, A., Dean, J., Devin, M., Ghemawat, S., Goodfellow, I., Harp, A., Irving, G.,
Isard, M., Jia, Y., Jozefowicz, R., Kaiser, L., Kudlur, M., Levenberg, J., Mané, D.,
Monga, R., Moore, S., Murray, D., Olah, C., Schuster, M., Shlens, J., Steiner, B.,
Sutskever, I., Talwar, K., Tucker, P., Vanhoucke, V., Vasudevan, V., Viégas, F.,
## Vinyals, O., Warden, P., Wattenberg, M., Wicke, M., Yu, Y., Zheng, X., 2015.
TensorFlow: Large-scale machine learning on heterogeneous systems. URL: https:
//www.tensorflow.org/. Software available from tensorflow.org.
van Amerongen, R.A., 1989. A general-purpose version of the fast decoupled loadflow.
IEEE Trans. Power Syst. 4 (2), 760–770. http://dx.doi.org/10.1109/59.193851.
## 10

T.B. Lopez-Garcia and J.A. Domínguez-NavarroEngineering Applications of Artificial Intelligence 117 (2023) 105567
Avelar, P.H.C., Lemos, H., Prates, M.O.R., Gori, M., Lamb, L., 2019. Typed graph
networks. ArXiv abs/1901.07984.
Babatunde, O., Munda, J., Hamam, Y., 2020. Power system flexibility: A review.
Energy Rep. 6, 101–106. http://dx.doi.org/10.1016/j.egyr.2019.11.048, The 6th
International Conference on Power and Energy Systems Engineering.
Battaglia, P.W., Hamrick, J.B., Bapst, V., Sanchez-Gonzalez, A., Zambaldi, V., Mali-
nowski, M., Tacchetti, A., Raposo, D., Santoro, A., Faulkner, R., Gulcehre, C.,
## Song, F., Ballard, A., Gilmer, J., Dahl, G., Vaswani, A., Allen, K., Nash, C.,
Langston, V., Dyer, C., Heess, N., Wierstra, D., Kohli, P., Botvinick, M., Vinyals, O.,
Li, Y., Pascanu, R., 2018. Relational inductive biases, deep learning, and graph
networks. arXiv.
## Donon, B., Clément, R., Donnot, B., Marot, A., Guyon, I., Schoenauer, M., 2020.
Neural networks for power flow: Graph neural solver. Electr. Power Syst. Res.
189, http://dx.doi.org/10.1016/j.epsr.2020.106547.
Fikri, M., Cheddadi, B., Sabri, O., Haidi, T., Abdelaziz, B., Majdoub, M., 2018. Power
flow analysis by numerical techniques and artificial neural networks. In: 3rd
Renewable Energies, Power Systems and Green Inclusive Economy, REPS and
GIE 2018. Institute of Electrical and Electronics Engineers Inc., pp. 1–5. http:
//dx.doi.org/10.1109/REPSGIE.2018.8488870.
Gilmer, J., Schoenholz, S.S., Riley, P.F., Vinyals, O., Dahl, G.E., 2017. Neural Message
Passing for Quantum Chemistry. In: JMLR.org (Ed.), International Conference on
Machine Learning. Sydney, pp. 1263–1272. http://dx.doi.org/10.5555/3305381.
## 3305512.
Glover, J.D., Sarma, M.S., Overbye, T.J., 2012. Power System Analysis and Design, fifth
ed. Cengage Learning.
Hu, X., Hu, H., Verma, S., Zhang, Z.-L., 2021. Physics-Guided Deep Neural Networks
for Power Flow Analysis. IEEE Trans. Power Syst. 36 (3), 2082–2092. http://dx.
doi.org/10.1109/TPWRS.2020.3029557.
Kipf, T.N., Welling, M., 2017. Semi-supervised classification with graph convolutional
networks. In: 5th International Conference on Learning Representations, ICLR 2017,
Toulon, France, April 24-26, 2017, Conference Track Proceedings. OpenReview.net.
Lopez-Garcia, T.B., Coronado-Mendoza, A., Domínguez-Navarro, J.A., 2020. Artificial
neural networks in microgrids: A review. Eng. Appl. Artif. Intell. 95, http://dx.doi.
org/10.1016/j.engappai.2020.103894.
## Owerko, D., Gama, F., Ribeiro, A., 2020. Optimal Power Flow Using Graph Neural
Networks. In: IEEE International Conference on Acoustics, Speech and Signal
Processing. ICASSP, pp. 5930–5934. http://dx.doi.org/10.1109/ICASSP40776.2020.
## 9053140.
Smith, O., Cattell, O., Farcot, E., O’Dea, R.D., Hopcraft, K.I., 2022. The effect of
renewable energy incorporation on power grid stability and resilience. Sci. Adv.
9 (8), 760–770. http://dx.doi.org/10.1126/sciadv.abj6734.
Stott, B., 1974. Review of load-flow calculation methods. Proc. IEEE 62 (7), 916–929.
Topping, J., Giovanni, F.D., Chamberlain, B.P., Dong, X., Bronstein, M.M., 2022. Under-
standing over-squashing and bottlenecks on graphs via curvature. In: International
Conference on Learning Representations. URL: https://openreview.net/forum?id=
7UmjRGzp-A.
Tovar-Facio, J., Martín, M., Ponce-Ortega, J.M., 2021. Sustainable energy transition:
modeling and optimization. Curr. Opin. Chem. Eng. 31, 100661. http://dx.doi.org/
## 10.1016/j.coche.2020.100661.
Van Hertern, D., Verboornen, J., Purchala, K., Belrnans, R., KlingH, W.L., 2006.
Usefulness of DC Power Flow for Active Power Flow Analysis with Flow Con-
trolling Devices. In: The 8th IEE International Conference on AC and DC Power
Transmission. IET, pp. 58–62. http://dx.doi.org/10.1049/cp:20060013.
Vankayala, V.S.S., Rao, N.D., 1993. Artificial neural networks and their applications to
power systems—a bibliographical survey. Electr. Power Syst. Res. 28 (1), 67–79.
Xie, L., Singh, C., Mitter, S.K., Dahleh, M.A., Oren, S.S., 2021. Toward carbon-neutral
electricity and mobility: Is the grid infrastructure ready? Joule 5 (8), 1908–1913.
http://dx.doi.org/10.1016/J.JOULE.2021.06.011.
Zimmerman, R., Murillo-Sanchez, C., Thomas, R., 2011. MATPOWER: Steady-State Op-
erations, Planning and Analysis Tools for Power Systems Research and Education,.
Power Syst. IEEE Trans. 26 (1), 12–19. http://dx.doi.org/10.1109/TPWRS.2010.
## 2051168.
## 11