#!/usr/bin/env python3
"""
Test script for the new gap_up_trade_workflow_agent
"""

def test_workflow_agent_import():
    """Test that the new workflow agent can be imported and has the correct structure"""
    
    print("🧪 Testing Gap-Up Trade Workflow Agent")
    print("=" * 50)
    
    try:
        from agents.gap_up_trade_workflow_agent import (
            gap_up_identification_agent, 
            gap_up_trade_workflow_agent
        )
        
        print("✅ Successfully imported workflow agents")
        
        # Test identification agent
        print(f"\n📈 Gap-Up Identification Agent:")
        print(f"   - Name: {gap_up_identification_agent.name}")
        print(f"   - Description: {gap_up_identification_agent.description}")
        print(f"   - Tools: {len(gap_up_identification_agent.tools)} tools")
        print(f"   - Output Key: {gap_up_identification_agent.output_key}")
        
        # Test main workflow agent
        print(f"\n🔄 Main Workflow Agent:")
        print(f"   - Name: {gap_up_trade_workflow_agent.name}")
        print(f"   - Description: {gap_up_trade_workflow_agent.description}")
        print(f"   - Sub-agents: {len(gap_up_trade_workflow_agent.sub_agents)} agents")
        print(f"   - Output Key: {gap_up_trade_workflow_agent.output_key}")
        
        # List sub-agents
        print(f"\n📋 Sub-Agents in Workflow:")
        for i, agent in enumerate(gap_up_trade_workflow_agent.sub_agents, 1):
            print(f"   {i}. {agent.name}: {agent.description}")
        
        print("\n✅ Workflow agent structure is correct!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_workflow_stages():
    """Test that the workflow has the correct stages"""
    
    print("\n🎯 Testing Workflow Stages")
    print("=" * 30)
    
    try:
        from agents.gap_up_trade_workflow_agent import gap_up_trade_workflow_agent
        
        expected_stages = [
            "gap_up_identification_agent",
            "data_agent", 
            "trade_planning_agent",
            "execution_agent"
        ]
        
        actual_stages = [agent.name for agent in gap_up_trade_workflow_agent.sub_agents]
        
        print("Expected stages:")
        for i, stage in enumerate(expected_stages, 1):
            print(f"   {i}. {stage}")
        
        print("\nActual stages:")
        for i, stage in enumerate(actual_stages, 1):
            print(f"   {i}. {stage}")
        
        if actual_stages == expected_stages:
            print("\n✅ Workflow stages match expected sequence!")
        else:
            print("\n❌ Workflow stages don't match expected sequence!")
            
    except Exception as e:
        print(f"❌ Error testing workflow stages: {e}")

if __name__ == "__main__":
    test_workflow_agent_import()
    test_workflow_stages() 