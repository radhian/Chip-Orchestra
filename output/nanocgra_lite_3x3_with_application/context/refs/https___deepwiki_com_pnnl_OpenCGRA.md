pnnl/OpenCGRA | DeepWiki
Loading...

Index your code with Devin
DeepWiki DeepWiki pnnl/OpenCGRA

Index your code with

Devin
Edit Wiki Share

Loading...

Last indexed: 3 May 2025 ( 2526bd )

OpenCGRA Overview
Installation and Setup
CGRA Architecture
Tile Structure
Functional Units
Basic Functional Units
Composite Functional Units
Control System
Memory System
Data Flow Graphs
Operations and Messages
Systolic Array Implementation
Testing and Verification
Advanced Configuration

Menu

OpenCGRA Overview

Relevant source files

.gitignore

.travis.yml

README.md

codecov.yml

OpenCGRA is a parameterizable and powerful Coarse-Grained Reconfigurable Arrays (CGRA) generator that produces synthesizable Verilog code for different CGRA architectures based on user-specified configurations. This document provides a high-level overview of the OpenCGRA project, including its purpose, key features, architecture, and main components. For detailed installation instructions, see Installation and Setup .

Sources: README.md 13-14

Purpose and Core Capabilities

OpenCGRA aims to simplify the design and implementation of CGRAs by providing:

Parameterized Generation : Create custom CGRA designs by specifying parameters such as array dimensions, functional unit types, and interconnection patterns

Modular Design : Component-based architecture with standardized interfaces for easy extension and modification

Verilog Generation : Automatic production of synthesizable Verilog for hardware implementation

Flexible Architecture : Support for various CGRA configurations from simple homogeneous arrays to complex heterogeneous designs

The framework is designed to support both research exploration and industrial application by offering a high degree of customization while maintaining hardware implementability.

Sources: README.md 13-14

High-Level Architecture

OpenCGRA is organized into several key subsystems that work together to define, configure, and execute computations on a CGRA.

System Architecture Overview

The diagram shows the main components of OpenCGRA:

Data Flow Graph (DFG) : Represents computations to be executed on the CGRA

Control System : Translates DFGs into configuration information

CGRARTL : The core hardware description containing the configurable CGRA

Functional Units : Computational elements that perform operations

Memory System : Handles data storage and retrieval

Systolic Array : Specialized implementation for specific application domains

Sources: README.md 14

CGRA Architecture

The CGRA is composed of a grid of computational tiles, with each tile containing functional units and routing resources.

CGRA Structure

Each tile in the CGRA contains:

FlexibleFuRTL : Configurable functional unit that can perform different operations

CrossbarRTL : Routing component for intra-tile and inter-tile communication

CtrlMemRTL : Storage for configuration and control signals

ConstQueueRTL : Queue for constant values used in computations

The tiles are arranged in a grid pattern, with the dimensions specified in the CGRA configuration.

Sources: README.md 14

Functional Units

Functional units are the computational building blocks of the CGRA. OpenCGRA provides a variety of FUs to support different operations.

Functional Unit Hierarchy

The functional units in OpenCGRA are categorized into:

Basic FUs :

AdderRTL : Addition operations

MulRTL : Multiplication operations

ShifterRTL : Bit shifting operations

BranchRTL : Conditional branching

CompRTL : Comparison operations

PhiRTL : Phi nodes for control flow

MemUnitRTL : Memory access operations

RetRTL : Return values

SelRTL : Selection operations

Composite FUs :

TwoSeqCombo : Sequential combination of two FUs

ThreeCombo : Sequential combination of three FUs

TwoPrlCombo : Parallel combination of two FUs

The FlexibleFuRTL component can be configured with different FUs and selects the appropriate one based on the operation being performed.

For more details on individual functional units, see Basic Functional Units and Composite Functional Units .

Sources: README.md 14

Workflow and Configuration

Programming and Execution Flow

The workflow for using OpenCGRA typically involves:

Defining the computation as a Data Flow Graph (DFG)

Generating control signals from the DFG

Configuring the CGRA with architecture parameters

Generating Verilog for the target implementation

Loading input data and executing the computation

Retrieving results after execution

For detailed information on working with Data Flow Graphs, see Data Flow Graphs .

Sources: README.md 129-133

Configuration Parameters

OpenCGRA provides extensive configuration options to customize the CGRA architecture:

Parameter Category Description Example Parameters Array Dimensions Size of the CGRA grid Width, Height Tile Configuration Components within each tile FU types, Crossbar connections Functional Units Available operations Basic FUs, Composite FUs Memory System Data storage configuration Memory size, Access patterns Interconnect Routing between tiles Network topology, Channel width
These parameters are specified when generating the CGRA design and affect the resulting Verilog implementation.

Sources: README.md 14

Implementation and Technology Stack

OpenCGRA is built on the PyMTL3 framework and uses several key technologies:

Component Role Python 3.7 Core implementation language PyMTL3 Hardware modeling framework Verilator Verilog simulation and verification Graphviz Visualization of designs
The system requires specific versions of these components to operate correctly:

Python: 3.7 (versions &lt;2.x and &gt;3.7 not supported)
PyMTL3: Custom fork (github.com/tancheng/pymtl3)
Verilator: 4.036 recommended

For installation instructions, see Installation and Setup .

Sources: README.md 40-45 .travis.yml 12-13 .travis.yml 36-37

Related Research

OpenCGRA has been used in several research publications:

&quot;AURORA: Automated Refinement of Coarse-Grained Reconfigurable Accelerators&quot; (DATE-21)

&quot;ARENA: Asynchronous Reconfigurable Accelerator Ring to Enable Data-Centric Parallel Computing&quot; (TPDS-21)

&quot;OpenCGRA: An Open-Source Framework for Modeling, Testing, and Evaluating CGRAs&quot; (ICCD-20)

These publications demonstrate applications and extensions of the OpenCGRA framework in various domains.

Sources: README.md 21-25

Further Documentation

For more detailed information on specific aspects of OpenCGRA, please refer to:

CGRA Architecture - Detailed architecture description

Functional Units - Information on computational elements

Control System - Details on configuration and control

Memory System - Memory architecture and access patterns

Data Flow Graphs - Computational representation

Systolic Array Implementation - Specialized implementation

Testing and Verification - Testing framework

Advanced Configuration - Advanced configuration options

Sources: README.md 14

Dismiss Refresh this wiki
Enter email to refresh

On this page
OpenCGRA Overview
Purpose and Core Capabilities
High-Level Architecture
System Architecture Overview
CGRA Architecture
CGRA Structure
Functional Units
Functional Unit Hierarchy
Workflow and Configuration
Programming and Execution Flow
Configuration Parameters
Implementation and Technology Stack
Related Research
Further Documentation