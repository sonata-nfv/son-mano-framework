pipeline {
  agent any
  stages {
    stage('Build') {
      parallel {
        stage('Service Lifecycle Manager') {
          steps {
            echo 'Building Service Lifecycle Manager container'
            sh './pipeline/build/servicelifecyclemanagement.sh'
          }
        }
        stage('Function Lifecycle Manager') {
          steps {
            echo 'Building Function Lifecycle Manager container'
            sh './pipeline/build/functionlifecyclemanagement.sh'
          }
        }
        stage('Plugin Manager') {
          steps {
            echo 'Building Plugin Manager container'
            sh './pipeline/build/pluginmanager.sh'
          }
        }
        stage('sonmanobase') {
          steps {
            echo 'Building sonmanobase container'
            sh './pipeline/build/sonmanobase.sh'
          }
        }
        stage('Specifc Manager Registry') {
          steps {
            echo 'Building Specific Manager Registry container'
            sh './pipeline/build/specificmanagerregistry.sh'
          }
        }
        stage('Placement Executive') {
          steps {
            echo 'Building Placement Executive container'
            sh './pipeline/build/placementexecutive.sh'
          }
        }
        stage('Placement Plugin') {
          steps {
            echo 'Building Placement Plugin container'
            sh './pipeline/build/placementplugin.sh'
          }
        }
      }
    }
  }
  post {
    success {
        emailext (
          subject: "SUCCESS: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'",
          body: """<p>SUCCESS: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':</p>
            <p>Check console output at &QUOT;<a href='${env.BUILD_URL}'>${env.JOB_NAME} [${env.BUILD_NUMBER}]</a>&QUOT;</p>""",
        recipientProviders: [[$class: 'DevelopersRecipientProvider']]
        )
      }
    failure {
      emailext (
          subject: "FAILED: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'",
          body: """<p>FAILED: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':</p>
            <p>Check console output at &QUOT;<a href='${env.BUILD_URL}'>${env.JOB_NAME} [${env.BUILD_NUMBER}]</a>&QUOT;</p>""",
          recipientProviders: [[$class: 'DevelopersRecipientProvider']]
        )
    }  
  }
}