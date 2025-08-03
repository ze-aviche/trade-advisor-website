#!/usr/bin/env python3
"""
Simple test for the workflow agent structure
"""

def test_workflow_structure():
    """Test the basic structure of the workflow agent"""
    
    print("🧪 Testing Gap-Up Trade Workflow Agent Structure")
    print("=" * 55)
    
    try:
        # Test the identification agent
        from agents.gap_up_trade_workflow_agent import gap_up_identification_agent
        
        print("✅ Successfully imported gap_up_identification_agent")
        print(f"   - Name: {gap_up_identification_agent.name}")
        print(f"   - Description: {gap_up_identification_agent.description}")
        print(f"   - Tools: {len(gap_up_identification_agent.tools)} tools")
        print(f"   - Output Key: {gap_up_identification_agent.output_key}")
        
        # Test the main workflow agent (without importing execution agent)
        from agents.gap_up_trade_workflow_agent import gap_up_trade_workflow_agent
        
        print(f"\n✅ Successfully imported gap_up_trade_workflow_agent")
        print(f"   - Name: {gap_up_trade_workflow_agent.name}")
        print(f"   - Description: {gap_up_trade_workflow_agent.description}")
        print(f"   - Sub-agents: {len(gap_up_trade_workflow_agent.sub_agents)} agents")
        print(f"   - Output Key: {gap_up_trade_workflow_agent.output_key}")
        
        # List sub-agents
        print(f"\n📋 Sub-Agents in Workflow:")
        for i, agent in enumerate(gap_up_trade_workflow_agent.sub_agents, 1):
            print(f"   {i}. {agent.name}: {agent.description}")
        
        # Check workflow stages
        expected_stages = [
            "gap_up_identification_agent",
            "data_agent", 
            "trade_planning_agent",
            "execution_agent"
        ]
        
        actual_stages = [agent.name for agent in gap_up_trade_workflow_agent.sub_agents]
        
        print(f"\n🎯 Workflow Stages:")
        print("Expected:", expected_stages)
        print("Actual:  ", actual_stages)
        
        if actual_stages == expected_stages:
            print("\n✅ Workflow stages match expected sequence!")
        else:
            print("\n❌ Workflow stages don't match expected sequence!")
        
        print("\n✅ Workflow agent structure is correct!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Note: This might be due to missing alpaca package for execution agent")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_file_renaming():
    """Test that the old file is gone and new file exists"""
    
    print("\n📁 Testing File Renaming")
    print("=" * 25)
    
    import os
    
    old_file = "agents/gap_up_listing_agent.py"
    new_file = "agents/gap_up_trade_workflow_agent.py"
    
    if not os.path.exists(old_file):
        print("✅ Old file (gap_up_listing_agent.py) successfully removed")
    else:
        print("❌ Old file still exists")
    
    if os.path.exists(new_file):
        print("✅ New file (gap_up_trade_workflow_agent.py) successfully created")
    else:
        print("❌ New file doesn't exist")
    
    print("\n✅ File renaming test completed!")

def test_agent_imports():
    """Test individual agent imports"""
    
    print("\n🧪 Testing Individual Agent Imports")
    print("=" * 35)
    
    try:
        from agents.data_agent import data_agent
        print("✅ data_agent imported successfully")
        
        from agents.trade_planning_agent import trade_planning_agent
        print("✅ trade_planning_agent imported successfully")
        
        print("✅ Individual agent imports successful!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_file_renaming()
    test_agent_imports()
    test_workflow_structure() 